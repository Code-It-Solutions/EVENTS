from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.delegate import Delegate
from app.models.payment import Payment
from app.models.event import Event
from app.forms import PaymentForm, CashPaymentForm
from app.services.mpesa import MpesaAPI

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

# Roles allowed to confirm cash payments
PAYMENT_CONFIRMATION_ROLES = ['finance', 'treasurer', 'admin', 'super_admin', 'registrar']


@payments_bp.route('/')
@login_required
def payment_page():
    """Show payment page with unpaid delegates"""
    # Get unpaid delegates that require payment (exclude fee-exempt categories)
    # Also exclude delegates already linked to a pending payment
    all_unpaid = Delegate.query.filter(
        Delegate.registered_by == current_user.id,
        Delegate.is_paid == False,
        Delegate.payment_id == None  # Not already linked to a payment
    ).all()
    
    # Get delegates pending finance approval
    pending_approval_delegates = Delegate.query.filter(
        Delegate.registered_by == current_user.id,
        Delegate.is_paid == False,
        Delegate.payment_id != None  # Linked to a pending payment
    ).all()
    
    # Separate fee-exempt and fee-required delegates
    unpaid_delegates = [d for d in all_unpaid if not d.is_fee_exempt()]
    fee_exempt_delegates = [d for d in all_unpaid if d.is_fee_exempt()]
    
    # Calculate total based on each delegate's fee
    total_amount = sum(d.get_registration_fee() for d in unpaid_delegates) if unpaid_delegates else 0
    delegate_fee = current_app.config.get('DELEGATE_FEE', 500)
    
    form = PaymentForm()
    if current_user.phone:
        form.phone_number.data = current_user.phone
    
    # Check if user can confirm cash payments (Finance for any, chairs for their own)
    # Since payment_page only shows the user's own delegates, chairs can confirm cash for those
    can_confirm_cash = current_user.role in PAYMENT_CONFIRMATION_ROLES or current_user.role == 'chair'
    
    # Get recent payment attempts
    recent_payments = Payment.query.filter_by(
        user_id=current_user.id
    ).order_by(Payment.created_at.desc()).limit(5).all()
    
    return render_template('payments/payment.html',
        form=form,
        unpaid_delegates=unpaid_delegates,
        pending_approval_delegates=pending_approval_delegates,
        fee_exempt_delegates=fee_exempt_delegates,
        total_amount=total_amount,
        delegate_fee=delegate_fee,
        recent_payments=recent_payments,
        can_confirm_cash=can_confirm_cash
    )


@payments_bp.route('/initiate', methods=['POST'])
@login_required
def initiate_payment():
    """Initiate payment based on selected method"""
    form = PaymentForm()
    
    current_app.logger.info(f'Payment initiate request - Form data: {request.form}')
    
    if not form.validate_on_submit():
        current_app.logger.error(f'Form validation failed: {form.errors}')
        flash('Please fill in the required fields.', 'danger')
        return redirect(url_for('payments.payment_page'))
    
    payment_method = form.payment_method.data
    current_app.logger.info(f'Payment method selected: {payment_method}')
    
    # Get unpaid delegates that require payment (exclude fee-exempt)
    # Also exclude delegates already linked to a pending payment
    all_unpaid = Delegate.query.filter(
        Delegate.registered_by == current_user.id,
        Delegate.is_paid == False,
        Delegate.payment_id == None  # Not already linked to a payment
    ).all()
    
    unpaid_delegates = [d for d in all_unpaid if not d.is_fee_exempt()]
    
    if not unpaid_delegates:
        flash('No unpaid delegates to process.', 'info')
        return redirect(url_for('main.dashboard'))
    
    # Calculate total based on each delegate's fee
    total_amount = sum(d.get_registration_fee() for d in unpaid_delegates)
    delegate_fee = current_app.config.get('DELEGATE_FEE', 500)
    
    if payment_method == 'mpesa':
        # M-Pesa STK Push
        if not form.phone_number.data:
            flash('Phone number is required for M-Pesa payment.', 'danger')
            return redirect(url_for('payments.payment_page'))
        return initiate_mpesa_payment(form, unpaid_delegates, total_amount, delegate_fee)
    
    elif payment_method == 'cash':
        # Cash payment - chairs can confirm for their own delegates, finance for any
        # Since we already filter by registered_by=current_user.id, chairs can only affect their own delegates
        current_app.logger.info(f'Processing cash payment for {len(unpaid_delegates)} delegates by {current_user.role}')
        return record_cash_payment(form, unpaid_delegates, total_amount, delegate_fee)
    
    elif payment_method in ['mpesa_paybill', 'bank_transfer']:
        # Manual verification required
        if not form.receipt_number.data:
            flash('Receipt/reference number is required for manual verification.', 'danger')
            return redirect(url_for('payments.payment_page'))
        return record_manual_payment(form, unpaid_delegates, total_amount, delegate_fee, payment_method)
    
    flash('Invalid payment method selected.', 'danger')
    return redirect(url_for('payments.payment_page'))


def initiate_mpesa_payment(form, unpaid_delegates, total_amount, delegate_fee):
    """Handle M-Pesa STK Push payment"""
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        amount=total_amount,
        payment_mode='M-Pesa STK Push',
        phone_number=form.phone_number.data,
        delegates_count=len(unpaid_delegates),
        status='pending'
    )
    db.session.add(payment)
    db.session.commit()
    
    # Link delegates to this payment
    for delegate in unpaid_delegates:
        delegate.payment_id = payment.id
    db.session.commit()
    
    # Initiate M-Pesa STK Push
    mpesa = MpesaAPI()
    response = mpesa.stk_push(
        phone_number=form.phone_number.data,
        amount=total_amount,
        account_reference=f"KAYO-{payment.id}",
        transaction_desc=f"Payment for {len(unpaid_delegates)} delegates"
    )
    
    if 'error' in response:
        payment.mark_failed('0', response['error'])
        db.session.commit()
        flash(f'Payment initiation failed: {response["error"]}', 'danger')
        return redirect(url_for('payments.payment_page'))
    
    # Update payment with M-Pesa response
    payment.checkout_request_id = response.get('CheckoutRequestID')
    payment.merchant_request_id = response.get('MerchantRequestID')
    db.session.commit()
    
    flash('Payment request sent! Check your phone to complete the payment.', 'success')
    return redirect(url_for('payments.payment_status', payment_id=payment.id))


def record_cash_payment(form, unpaid_delegates, total_amount, delegate_fee):
    """Handle cash payment confirmation - sets status to pending finance approval for chairs"""
    try:
        # Double-check: filter out any delegates that already have a payment_id (race condition protection)
        unpaid_delegates = [d for d in unpaid_delegates if d.payment_id is None]
        
        if not unpaid_delegates:
            flash('All selected delegates already have pending payments.', 'warning')
            return redirect(url_for('payments.payment_page'))
        
        # Recalculate total after filtering
        total_amount = sum(d.get_registration_fee() for d in unpaid_delegates)
        
        # Determine if this is a chair submitting (needs finance approval) or finance directly confirming
        is_chair = current_user.role == 'chair'
        is_finance = current_user.role in ['finance', 'treasurer', 'admin', 'super_admin']
        
        # Set finance status based on who is confirming
        if is_finance:
            finance_status = 'approved'
            payment_status = 'completed'
            completed_at = datetime.utcnow()
        else:
            # Chair confirmation - needs finance approval
            finance_status = 'pending_approval'
            payment_status = 'pending'
            completed_at = None
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            amount=total_amount,
            payment_mode='Cash',
            mpesa_receipt_number=form.receipt_number.data or f"CASH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            delegates_count=len(unpaid_delegates),
            status=payment_status,
            finance_status=finance_status,
            confirmed_by_chair_id=current_user.id if is_chair else None,
            confirmed_by_chair_at=datetime.utcnow() if is_chair else None,
            approved_by_finance_id=current_user.id if is_finance else None,
            approved_by_finance_at=datetime.utcnow() if is_finance else None,
            completed_at=completed_at
        )
        db.session.add(payment)
        db.session.flush()  # Get the payment.id without committing
        
        payment_id = payment.id
        delegate_ids = [d.id for d in unpaid_delegates]
        now = datetime.utcnow()
        
        current_app.logger.info(f'Recording cash payment for delegates: {delegate_ids}, finance_status: {finance_status}')
        
        # Use direct UPDATE query to ensure changes are persisted
        tickets_issued = 0
        for delegate in unpaid_delegates:
            # Get the correct fee for this delegate
            delegate_specific_fee = delegate.get_registration_fee()
            
            # Link delegate to payment but only mark as paid if finance approved
            update_data = {
                'payment_id': payment_id,
                'amount_paid': delegate_specific_fee,
            }
            
            # Only mark as fully paid and issue tickets if finance has approved
            if is_finance:
                # Generate ticket number if not already assigned
                new_ticket = None
                if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                    event = Event.query.get(delegate.event_id) if delegate.event_id else None
                    new_ticket = Delegate.generate_ticket_number(event)
                    tickets_issued += 1
                
                update_data['is_paid'] = True
                update_data['payment_confirmed_by'] = current_user.id
                update_data['payment_confirmed_at'] = now
                if new_ticket:
                    update_data['ticket_number'] = new_ticket
            
            db.session.query(Delegate).filter(Delegate.id == delegate.id).update(update_data)
        
        db.session.commit()
        
        # Verify the update worked
        updated_delegate = Delegate.query.get(delegate_ids[0])
        current_app.logger.info(f'Cash payment recorded: {payment_id}, finance_status: {finance_status}')
        
        if is_finance:
            flash(f'Cash payment of KSh {total_amount:,.2f} confirmed for {len(unpaid_delegates)} delegate(s). {tickets_issued} ticket(s) issued.', 'success')
            return redirect(url_for('payments.payment_page'))
        else:
            flash(f'Cash payment of KSh {total_amount:,.2f} submitted for {len(unpaid_delegates)} delegate(s). Awaiting Finance approval.', 'info')
            return redirect(url_for('payments.my_submissions'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error recording cash payment: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error recording payment: {str(e)}', 'danger')
        return redirect(url_for('payments.payment_page'))


def record_manual_payment(form, unpaid_delegates, total_amount, delegate_fee, payment_method):
    """Handle manual payment verification (paybill/bank transfer) - needs finance approval for chairs"""
    try:
        payment_mode = 'M-Pesa Paybill' if payment_method == 'mpesa_paybill' else 'Bank Transfer'
        
        # Determine if this is a chair submitting (needs finance approval) or finance directly confirming
        is_chair = current_user.role == 'chair'
        is_finance = current_user.role in ['finance', 'treasurer', 'admin', 'super_admin']
        
        # Set finance status based on who is confirming
        if is_finance:
            finance_status = 'approved'
            payment_status = 'completed'
            completed_at = datetime.utcnow()
        else:
            # Chair confirmation - needs finance approval
            finance_status = 'pending_approval'
            payment_status = 'pending'
            completed_at = None
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            amount=total_amount,
            payment_mode=payment_mode,
            mpesa_receipt_number=form.receipt_number.data,
            phone_number=form.phone_number.data,
            delegates_count=len(unpaid_delegates),
            status=payment_status,
            finance_status=finance_status,
            confirmed_by_chair_id=current_user.id if is_chair else None,
            confirmed_by_chair_at=datetime.utcnow() if is_chair else None,
            approved_by_finance_id=current_user.id if is_finance else None,
            approved_by_finance_at=datetime.utcnow() if is_finance else None,
            completed_at=completed_at
        )
        db.session.add(payment)
        db.session.flush()  # Get the payment.id without committing
        
        payment_id = payment.id
        delegate_ids = [d.id for d in unpaid_delegates]
        now = datetime.utcnow()
        
        current_app.logger.info(f'Recording {payment_mode} payment for delegates: {delegate_ids}, finance_status: {finance_status}')
        
        # Use direct UPDATE query to ensure changes are persisted
        tickets_issued = 0
        for delegate in unpaid_delegates:
            # Get the correct fee for this delegate
            delegate_specific_fee = delegate.get_registration_fee()
            
            # Link delegate to payment
            update_data = {
                'payment_id': payment_id,
                'amount_paid': delegate_specific_fee,
            }
            
            # Only mark as fully paid and issue tickets if finance has approved
            if is_finance:
                # Generate ticket number if not already assigned
                new_ticket = None
                if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                    event = Event.query.get(delegate.event_id) if delegate.event_id else None
                    new_ticket = Delegate.generate_ticket_number(event)
                    tickets_issued += 1
                
                update_data['is_paid'] = True
                update_data['payment_confirmed_by'] = current_user.id
                update_data['payment_confirmed_at'] = now
                if new_ticket:
                    update_data['ticket_number'] = new_ticket
            
            db.session.query(Delegate).filter(Delegate.id == delegate.id).update(update_data)
        
        db.session.commit()
        
        # Verify the update worked
        updated_delegate = Delegate.query.get(delegate_ids[0])
        current_app.logger.info(f'{payment_mode} payment recorded: {payment_id}, finance_status: {finance_status}')
        
        if is_finance:
            flash(f'{payment_mode} payment confirmed for {len(unpaid_delegates)} delegate(s). {tickets_issued} ticket(s) issued.', 'success')
        else:
            flash(f'{payment_mode} payment submitted for {len(unpaid_delegates)} delegate(s). Awaiting Finance approval.', 'info')
        
        return redirect(url_for('payments.payment_status', payment_id=payment_id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error recording manual payment: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error recording payment: {str(e)}', 'danger')
        return redirect(url_for('payments.payment_page'))


@payments_bp.route('/confirm-cash', methods=['GET', 'POST'])
@login_required
def confirm_cash_payment():
    """Page for chairs/finance to confirm cash payments for delegates"""
    # Allow chairs and finance roles
    allowed_roles = ['chair', 'finance', 'treasurer', 'admin', 'super_admin']
    if current_user.role not in allowed_roles:
        flash('Access denied. Only Parish Chairs and Finance personnel can record cash payments.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CashPaymentForm()
    delegate_fee = current_app.config.get('DELEGATE_FEE', 500)
    
    # Get all unpaid delegates (excluding fee-exempt and those already linked to a pending payment)
    # For chairs, show delegates they registered OR delegates in their parish
    if current_user.role == 'chair':
        from sqlalchemy import or_
        all_unpaid = Delegate.query.filter(
            Delegate.is_paid == False,
            Delegate.payment_id == None,  # Not already linked to a payment
            or_(
                Delegate.registered_by == current_user.id,
                Delegate.parish == current_user.parish
            )
        ).order_by(
            Delegate.archdeaconry, Delegate.parish, Delegate.name
        ).all()
    else:
        all_unpaid = Delegate.query.filter(
            Delegate.is_paid == False,
            Delegate.payment_id == None  # Not already linked to a payment
        ).order_by(
            Delegate.archdeaconry, Delegate.parish, Delegate.name
        ).all()
    unpaid_delegates = [d for d in all_unpaid if not d.is_fee_exempt()]
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Parse delegate IDs
            delegate_ids = [int(id.strip()) for id in form.delegate_ids.data.split(',') if id.strip()]
            
            current_app.logger.info(f'Confirm cash payment request for delegate IDs: {delegate_ids}')
            
            if not delegate_ids:
                flash('Please select at least one delegate.', 'danger')
                return render_template('payments/confirm_cash.html', form=form, unpaid_delegates=unpaid_delegates, delegate_fee=delegate_fee)
            
            # Get delegates - only those without existing payment
            delegates = Delegate.query.filter(
                Delegate.id.in_(delegate_ids),
                Delegate.payment_id == None  # Verify no pending payment (race condition protection)
            ).all()
            
            if not delegates:
                flash('No eligible delegates found. They may have already been submitted for payment.', 'warning')
                return redirect(url_for('payments.confirm_cash_payment'))
            
            if len(delegates) < len(delegate_ids):
                skipped = len(delegate_ids) - len(delegates)
                flash(f'{skipped} delegate(s) skipped - already submitted for payment.', 'warning')
            
            # Calculate amount using each delegate's fee
            total_amount = sum(d.get_registration_fee() for d in delegates)
            
            # Determine if this is a chair (needs finance approval) or finance (direct approval)
            is_chair = current_user.role == 'chair'
            is_finance = current_user.role in ['finance', 'treasurer', 'admin', 'super_admin']
            
            # Set finance status based on who is confirming
            if is_finance:
                finance_status = 'approved'
                payment_status = 'completed'
                completed_at = datetime.utcnow()
            else:
                # Chair confirmation - needs finance approval
                finance_status = 'pending_approval'
                payment_status = 'pending'
                completed_at = None
            
            # Create payment record
            payment = Payment(
                user_id=current_user.id,
                amount=total_amount,
                payment_mode='Cash',
                mpesa_receipt_number=form.receipt_number.data or f"CASH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                result_desc=form.notes.data,
                delegates_count=len(delegates),
                status=payment_status,
                finance_status=finance_status,
                confirmed_by_chair_id=current_user.id if is_chair else None,
                confirmed_by_chair_at=datetime.utcnow() if is_chair else None,
                approved_by_finance_id=current_user.id if is_finance else None,
                approved_by_finance_at=datetime.utcnow() if is_finance else None,
                completed_at=completed_at
            )
            db.session.add(payment)
            db.session.flush()  # Get the payment.id without committing
            
            payment_id = payment.id
            now = datetime.utcnow()
            
            # Use direct UPDATE query to ensure changes are persisted
            tickets_issued = 0
            for delegate in delegates:
                # Get the correct fee for this delegate
                delegate_specific_fee = delegate.get_registration_fee()
                
                # Link delegate to payment
                update_data = {
                    'payment_id': payment_id,
                    'amount_paid': delegate_specific_fee,
                }
                
                # Only mark as paid and issue tickets if finance has approved
                if is_finance:
                    # Generate ticket number if not already assigned
                    new_ticket = None
                    if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                        event = Event.query.get(delegate.event_id) if delegate.event_id else None
                        new_ticket = Delegate.generate_ticket_number(event)
                        tickets_issued += 1
                    
                    update_data['is_paid'] = True
                    update_data['payment_confirmed_by'] = current_user.id
                    update_data['payment_confirmed_at'] = now
                    if new_ticket:
                        update_data['ticket_number'] = new_ticket
                
                db.session.query(Delegate).filter(Delegate.id == delegate.id).update(update_data)
            
            db.session.commit()
            
            # Log the result
            current_app.logger.info(f'Cash payment recorded: {payment_id}, finance_status: {finance_status}, by: {current_user.role}')
            
            if is_finance:
                flash(f'Cash payment confirmed for {len(delegates)} delegate(s). {tickets_issued} ticket(s) issued.', 'success')
            else:
                flash(f'Cash payment of KSh {total_amount:,.2f} submitted for {len(delegates)} delegate(s). Awaiting Finance approval.', 'info')
            
            return redirect(url_for('payments.my_submissions') if is_chair else url_for('payments.confirm_cash_payment'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error confirming cash payment: {str(e)}')
            import traceback
            current_app.logger.error(traceback.format_exc())
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('payments/confirm_cash.html', form=form, unpaid_delegates=unpaid_delegates, delegate_fee=delegate_fee)


@payments_bp.route('/status/<int:payment_id>')
@login_required
def payment_status(payment_id):
    """Show payment status page"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Only allow viewing own payments (unless admin)
    if payment.user_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to view this payment.', 'danger')
        return redirect(url_for('payments.payment_page'))
    
    return render_template('payments/status.html', payment=payment)


@payments_bp.route('/check-status/<int:payment_id>')
@login_required
def check_payment_status(payment_id):
    """API endpoint to check payment status"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Only allow checking own payments (unless admin)
    if payment.user_id != current_user.id and not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
    
    if payment.status != 'pending':
        return jsonify({
            'status': payment.status,
            'receipt': payment.mpesa_receipt_number
        })
    
    # Query M-Pesa for status
    if payment.checkout_request_id:
        mpesa = MpesaAPI()
        response = mpesa.query_stk_status(payment.checkout_request_id)
        
        result_code = response.get('ResultCode')
        if result_code is not None:
            if str(result_code) == '0':
                # Success
                payment.mark_completed(
                    mpesa_receipt=response.get('MpesaReceiptNumber', 'N/A')
                )
                db.session.commit()
            elif str(result_code) != '':
                # Failed
                payment.mark_failed(
                    result_code=str(result_code),
                    result_desc=response.get('ResultDesc', 'Payment failed')
                )
                # Unlink delegates from failed payment
                for delegate in payment.delegates:
                    delegate.payment_id = None
                db.session.commit()
    
    return jsonify({
        'status': payment.status,
        'receipt': payment.mpesa_receipt_number
    })


@payments_bp.route('/resend-stk/<int:payment_id>', methods=['POST'])
@login_required
def resend_stk(payment_id):
    """Resend M-Pesa STK push for a pending payment"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Only allow owner to resend
    if payment.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Only resend for pending M-Pesa payments
    if payment.status != 'pending' or not payment.checkout_request_id:
        return jsonify({'success': False, 'message': 'Invalid payment state'}), 400
    
    try:
        # Get phone number from original payment or user
        phone = payment.phone_number or current_user.phone
        if not phone:
            return jsonify({'success': False, 'message': 'No phone number available'}), 400
        
        # Initiate new STK push
        mpesa = MpesaAPI()
        response = mpesa.stk_push(
            phone=phone,
            amount=int(payment.amount),
            account_reference=f"KAYO-{payment.id}",
            transaction_desc=f"KAYO Delegate Payment"
        )
        
        if response.get('ResponseCode') == '0':
            # Update payment with new checkout request ID
            payment.checkout_request_id = response.get('CheckoutRequestID')
            payment.merchant_request_id = response.get('MerchantRequestID')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'STK push sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': response.get('errorMessage', 'Failed to send STK push')
            })
    except Exception as e:
        current_app.logger.error(f"Error resending STK: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@payments_bp.route('/cancel-and-retry/<int:payment_id>')
@login_required
def cancel_and_retry(payment_id):
    """Cancel pending M-Pesa payment and switch to cash/manual payment"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Only allow owner to cancel
    if payment.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Only cancel pending M-Pesa payments
    if payment.status != 'pending':
        flash('This payment cannot be modified.', 'warning')
        return redirect(url_for('payments.payment_page'))
    
    # Get the delegates linked to this payment
    delegates = list(payment.delegates)
    delegate_ids = [d.id for d in delegates]
    
    # Unlink delegates from the failed payment
    for delegate in delegates:
        delegate.payment_id = None
    
    # Mark payment as cancelled
    payment.status = 'failed'
    payment.result_desc = 'Cancelled by user - switching to alternative payment method'
    db.session.commit()
    
    # Store delegate IDs in session for the new payment
    from flask import session
    session['retry_delegate_ids'] = delegate_ids
    
    flash('M-Pesa payment cancelled. Please submit payment via Cash or Bank Transfer.', 'info')
    return redirect(url_for('payments.manual_payment_form'))


@payments_bp.route('/manual-payment', methods=['GET', 'POST'])
@login_required
def manual_payment_form():
    """Manual payment form for cash/bank transfer after STK timeout"""
    from flask import session
    
    # Get delegates from session or show all unpaid
    retry_delegate_ids = session.pop('retry_delegate_ids', None)
    
    if retry_delegate_ids:
        delegates = Delegate.query.filter(
            Delegate.id.in_(retry_delegate_ids),
            Delegate.registered_by == current_user.id
        ).all()
    else:
        delegates = Delegate.query.filter(
            Delegate.registered_by == current_user.id,
            Delegate.is_paid == False,
            Delegate.payment_id == None
        ).all()
    
    # Filter out fee-exempt delegates
    delegates = [d for d in delegates if not d.is_fee_exempt()]
    
    if not delegates:
        flash('No unpaid delegates found.', 'info')
        return redirect(url_for('payments.payment_page'))
    
    total_amount = sum(d.get_registration_fee() for d in delegates)
    
    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'cash')
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Create new payment record
        payment = Payment(
            user_id=current_user.id,
            amount=total_amount,
            delegates_count=len(delegates),
            status='pending',
            payment_mode=payment_method,
            finance_status='pending_approval',
            transaction_reference=reference,
            notes=notes
        )
        db.session.add(payment)
        db.session.flush()
        
        # Link delegates to payment
        for delegate in delegates:
            delegate.payment_id = payment.id
        
        db.session.commit()
        
        flash(f'Payment of KSh {total_amount:,.0f} submitted for {len(delegates)} delegate(s). Awaiting Finance approval.', 'success')
        return redirect(url_for('payments.payment_status', payment_id=payment.id))
    
    return render_template('payments/manual_payment.html',
        delegates=delegates,
        total_amount=total_amount
    )


@payments_bp.route('/callback', methods=['POST'])
def mpesa_callback():
    """M-Pesa callback endpoint"""
    data = request.get_json()
    
    current_app.logger.info(f"M-Pesa callback received: {data}")
    
    if not data:
        return jsonify({'ResultCode': 1, 'ResultDesc': 'No data received'})
    
    try:
        callback = data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = callback.get('CheckoutRequestID')
        result_code = callback.get('ResultCode')
        result_desc = callback.get('ResultDesc')
        
        # Find payment by checkout request ID
        payment = Payment.query.filter_by(checkout_request_id=checkout_request_id).first()
        
        if not payment:
            current_app.logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
            return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        if str(result_code) == '0':
            # Successful payment
            callback_metadata = callback.get('CallbackMetadata', {}).get('Item', [])
            mpesa_receipt = None
            transaction_date = None
            
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'TransactionDate':
                    transaction_date = item.get('Value')
            
            payment.mark_completed(mpesa_receipt=mpesa_receipt or 'N/A')
            db.session.commit()
            current_app.logger.info(f"Payment {payment.id} completed successfully")
        else:
            # Failed payment
            payment.mark_failed(result_code=str(result_code), result_desc=result_desc)
            # Unlink delegates from failed payment
            for delegate in payment.delegates:
                delegate.payment_id = None
            db.session.commit()
            current_app.logger.info(f"Payment {payment.id} failed: {result_desc}")
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})
    
    except Exception as e:
        current_app.logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return jsonify({'ResultCode': 1, 'ResultDesc': str(e)})


@payments_bp.route('/history')
@login_required
def payment_history():
    """Show payment history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    payments = Payment.query.filter_by(
        user_id=current_user.id
    ).order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('payments/history.html', payments=payments)


@payments_bp.route('/history/clear', methods=['POST'])
@login_required
def clear_history():
    """Clear payment history for current user (only failed/cancelled payments)"""
    # Only delete failed or cancelled payments, not completed ones
    deleted_count = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status.in_(['failed', 'cancelled', 'pending'])
    ).delete(synchronize_session=False)
    
    db.session.commit()
    
    if deleted_count > 0:
        flash(f'Cleared {deleted_count} failed/pending payment records.', 'success')
    else:
        flash('No failed or pending payments to clear.', 'info')
    
    return redirect(url_for('payments.payment_history'))


@payments_bp.route('/history/<int:payment_id>/delete', methods=['POST'])
@login_required
def delete_payment(payment_id):
    """Delete a specific payment record"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Finance roles that can delete any payment
    finance_roles = ['finance', 'treasurer', 'admin', 'super_admin']
    
    # Check permission - users can delete their own, finance/admins can delete any
    if payment.user_id != current_user.id and current_user.role not in finance_roles:
        flash('You do not have permission to delete this payment.', 'error')
        return redirect(url_for('payments.payment_history'))
    
    # Only allow deleting non-completed payments for regular users
    if payment.status == 'completed' and current_user.role not in finance_roles:
        flash('Cannot delete completed payments. Contact admin.', 'error')
        return redirect(url_for('payments.payment_history'))
    
    try:
        # Get the redirect URL before deletion
        redirect_url = request.form.get('redirect_url', url_for('payments.payment_history'))
        
        # Unlink all delegates from this payment and reset their payment status
        delegates_unlinked = 0
        for delegate in payment.delegates.all():
            delegate.payment_id = None
            delegate.is_paid = False
            delegate.amount_paid = 0
            delegate.payment_confirmed_by = None
            delegate.payment_confirmed_at = None
            delegates_unlinked += 1
        
        payment_amount = payment.amount
        payment_mode = payment.payment_mode
        
        db.session.delete(payment)
        db.session.commit()
        
        if delegates_unlinked > 0:
            flash(f'Payment of KES {payment_amount:,.2f} ({payment_mode}) deleted. {delegates_unlinked} delegate(s) unlinked and marked as unpaid.', 'success')
        else:
            flash('Payment record deleted.', 'success')
        
        return redirect(redirect_url)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting payment {payment_id}: {str(e)}')
        flash(f'Error deleting payment: {str(e)}', 'danger')
        return redirect(url_for('payments.payment_history'))


# ==================== CHAIR SUBMITTED PAYMENTS ====================

@payments_bp.route('/my-submissions')
@login_required
def my_submissions():
    """Show payments submitted by chair for finance approval"""
    # This route is for chairs to track their submitted payments
    if current_user.role not in ['chair', 'admin', 'super_admin']:
        flash('This page is for parish chairs only.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    # Get payments submitted by this chair
    submitted_payments = Payment.query.filter(
        Payment.confirmed_by_chair_id == current_user.id
    ).order_by(Payment.created_at.desc()).all()
    
    # Separate by status
    pending = [p for p in submitted_payments if p.finance_status == 'pending_approval']
    approved = [p for p in submitted_payments if p.finance_status == 'approved']
    rejected = [p for p in submitted_payments if p.finance_status == 'rejected']
    
    # Calculate totals
    total_pending = sum(p.amount for p in pending)
    total_approved = sum(p.amount for p in approved)
    
    return render_template('payments/my_submissions.html',
                         pending=pending,
                         approved=approved,
                         rejected=rejected,
                         total_pending=total_pending,
                         total_approved=total_approved)


# ==================== FINANCE PAYMENT MANAGEMENT ====================

@payments_bp.route('/finance/dashboard')
@login_required
def finance_payment_dashboard():
    """Finance dashboard for payment verification, approval, and receipt"""
    if current_user.role not in ['finance', 'admin', 'super_admin']:
        flash('Access denied. Finance personnel only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get all payments grouped by status
    pending_payments = Payment.query.filter_by(status='pending').order_by(Payment.created_at.desc()).all()
    completed_payments = Payment.query.filter_by(status='completed').order_by(Payment.completed_at.desc()).limit(50).all()
    failed_payments = Payment.query.filter_by(status='failed').order_by(Payment.created_at.desc()).limit(20).all()
    
    # Stats
    total_pending = sum(p.amount for p in pending_payments)
    total_completed = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    total_today = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.status == 'completed',
        Payment.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
    ).scalar() or 0
    
    # Count delegates paid vs unpaid
    total_delegates = Delegate.query.count()
    paid_delegates = Delegate.query.filter_by(is_paid=True).count()
    
    return render_template('payments/finance_dashboard.html',
        pending_payments=pending_payments,
        completed_payments=completed_payments,
        failed_payments=failed_payments,
        total_pending=total_pending,
        total_completed=total_completed,
        total_today=total_today,
        total_delegates=total_delegates,
        paid_delegates=paid_delegates
    )


@payments_bp.route('/finance/verify/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def verify_payment(payment_id):
    """Verify a pending payment"""
    if current_user.role not in ['finance', 'admin', 'super_admin']:
        flash('Access denied. Finance personnel only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    payment = Payment.query.get_or_404(payment_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        notes = request.form.get('notes', '')
        
        if action == 'approve':
            payment.status = 'completed'
            payment.completed_at = datetime.utcnow()
            payment.result_desc = f"Verified by {current_user.name}. {notes}"
            
            # Update delegates linked to this payment
            delegates = Delegate.query.filter_by(payment_id=payment.id).all()
            for delegate in delegates:
                delegate.is_paid = True
                delegate.paid_at = datetime.utcnow()
                if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                    event = Event.query.get(delegate.event_id) if delegate.event_id else None
                    delegate.ticket_number = Delegate.generate_ticket_number(event)
            
            db.session.commit()
            flash(f'Payment verified and approved. {len(delegates)} delegate(s) marked as paid.', 'success')
        
        elif action == 'reject':
            payment.status = 'failed'
            payment.result_desc = f"Rejected by {current_user.name}. Reason: {notes}"
            db.session.commit()
            flash('Payment rejected.', 'warning')
        
        return redirect(url_for('payments.finance_payment_dashboard'))
    
    # Get linked delegates
    delegates = Delegate.query.filter_by(payment_id=payment.id).all()
    
    return render_template('payments/verify_payment.html',
        payment=payment,
        delegates=delegates
    )


@payments_bp.route('/finance/receive', methods=['GET', 'POST'])
@login_required
def receive_payment():
    """Receive cash/manual payment from chair - for direct payments (not pending approval)"""
    if current_user.role not in ['finance', 'admin', 'super_admin']:
        flash('Access denied. Finance personnel only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    delegate_fee = current_app.config.get('DELEGATE_FEE', 500)
    
    # Get all unpaid delegates grouped by chair
    # Exclude delegates that already have a pending payment (payment_id is set)
    from app.models.user import User
    chairs = User.query.filter(User.role.in_(['chair', 'registration_officer', 'data_clerk'])).all()
    
    unpaid_by_chair = {}
    for chair in chairs:
        # Only get delegates without a pending payment
        unpaid = Delegate.query.filter(
            Delegate.registered_by == chair.id,
            Delegate.is_paid == False,
            Delegate.payment_id == None  # No pending payment
        ).all()
        # Filter out fee-exempt delegates
        unpaid = [d for d in unpaid if not d.is_fee_exempt()]
        if unpaid:
            unpaid_by_chair[chair] = unpaid
    
    # Count pending approvals for info
    pending_approval_count = Payment.query.filter_by(finance_status='pending_approval').count()
    
    if request.method == 'POST':
        delegate_ids = request.form.getlist('delegate_ids')
        receipt_number = request.form.get('receipt_number', '')
        notes = request.form.get('notes', '')
        
        if not delegate_ids:
            flash('Please select at least one delegate.', 'warning')
            return redirect(url_for('payments.receive_payment'))
        
        # Get delegates - only those without pending payment (race condition protection)
        delegates = Delegate.query.filter(
            Delegate.id.in_(delegate_ids),
            Delegate.payment_id == None
        ).all()
        
        if not delegates:
            flash('All selected delegates already have pending payments.', 'warning')
            return redirect(url_for('payments.receive_payment'))
        
        # Calculate total based on each delegate's actual fee
        total_amount = sum(d.get_registration_fee() for d in delegates)
        
        # Create payment record - finance directly approves
        payment = Payment(
            user_id=current_user.id,
            amount=total_amount,
            payment_mode='Cash',
            mpesa_receipt_number=receipt_number or f"CASH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            result_desc=f"Cash received by {current_user.name}. {notes}",
            delegates_count=len(delegates),
            status='completed',
            finance_status='approved',
            approved_by_finance_id=current_user.id,
            approved_by_finance_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(payment)
        db.session.flush()
        
        # Update delegates
        tickets_issued = 0
        for delegate in delegates:
            delegate.payment_id = payment.id
            delegate.is_paid = True
            delegate.amount_paid = delegate.get_registration_fee()
            delegate.payment_confirmed_by = current_user.id
            delegate.payment_confirmed_at = datetime.utcnow()
            if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                event = Event.query.get(delegate.event_id) if delegate.event_id else None
                delegate.ticket_number = Delegate.generate_ticket_number(event)
                tickets_issued += 1
        
        db.session.commit()
        flash(f'Payment received for {len(delegates)} delegate(s). Total: KSh {total_amount:,.0f}. {tickets_issued} ticket(s) issued.', 'success')
        return redirect(url_for('payments.finance_payment_dashboard'))
    
    return render_template('payments/receive_payment.html',
        unpaid_by_chair=unpaid_by_chair,
        delegate_fee=delegate_fee,
        pending_approval_count=pending_approval_count
    )


@payments_bp.route('/finance/all')
@login_required
def all_payments():
    """View all payments in the system"""
    if current_user.role not in ['finance', 'admin', 'super_admin']:
        flash('Access denied. Finance personnel only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    status_filter = request.args.get('status', '')
    method_filter = request.args.get('method', '')
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    
    query = Payment.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    if method_filter:
        query = query.filter_by(payment_mode=method_filter)
    
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(Payment.created_at >= from_dt)
        except ValueError:
            pass
    
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Payment.created_at <= to_dt)
        except ValueError:
            pass
    
    payments = query.order_by(Payment.created_at.desc()).all()
    
    return render_template('payments/all_payments.html',
        payments=payments,
        status_filter=status_filter
    )


@payments_bp.route('/finance/export')
@login_required
def export_payments():
    """Export payments to CSV"""
    if current_user.role not in ['finance', 'admin', 'super_admin']:
        flash('Access denied. Finance personnel only.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    from flask import Response
    import csv
    from io import StringIO
    
    status_filter = request.args.get('status', '')
    
    query = Payment.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    payments = query.order_by(Payment.created_at.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Transaction ID', 'Delegate', 'Phone', 'Amount', 'Method', 'Status', 'Date', 'Receipt', 'Notes'])
    
    for p in payments:
        delegates_list = p.delegates.all()
        delegate_name = delegates_list[0].name if delegates_list else 'N/A'
        if len(delegates_list) > 1:
            delegate_name = f"{delegate_name} (+{len(delegates_list)-1} more)"
        writer.writerow([
            p.id,
            p.transaction_id or p.mpesa_receipt_number or '',
            delegate_name,
            p.phone_number or '',
            p.amount,
            p.payment_mode or '',
            p.status,
            p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else '',
            p.mpesa_receipt_number or '',
            p.result_desc or ''
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=payments_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'}
    )


