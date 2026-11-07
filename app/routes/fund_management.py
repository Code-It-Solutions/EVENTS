"""
Fund Management Routes
- Pledges tracking
- Scheduled payments
- Fund transfers (Chair -> Finance)
"""
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import (
    User, Delegate, Event,
    Pledge, PledgePayment, ScheduledPayment, ScheduledPaymentInstallment,
    FundTransfer, FundTransferApproval, PaymentSummary
)
from app.forms import (
    PledgeForm, PledgePaymentForm, ScheduledPaymentForm, InstallmentPaymentForm,
    FundTransferForm, FundTransferApprovalForm, FundTransferCompleteForm, PaymentConfirmationForm,
    EmptyForm
)
from functools import wraps

bp = Blueprint('fund_management', __name__, url_prefix='/funds')


def role_required(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============== DASHBOARD ==============

@bp.route('/dashboard')
@login_required
def dashboard():
    """Fund management dashboard based on user role"""
    if current_user.role == 'finance' or current_user.role == 'admin' or current_user.role == 'super_admin':
        return redirect(url_for('fund_management.finance_dashboard'))
    else:
        return redirect(url_for('fund_management.chair_dashboard'))


@bp.route('/chair/dashboard')
@login_required
def chair_dashboard():
    """Dashboard for chairs to track payments and pledges"""
    # Get current event
    event = current_user.get_current_event()
    
    # Get pledges recorded by this chair
    pledges = Pledge.query.filter_by(recorded_by=current_user.id).order_by(Pledge.created_at.desc()).all()
    
    # Get scheduled payments
    scheduled_payments = ScheduledPayment.query.filter_by(recorded_by=current_user.id).order_by(ScheduledPayment.created_at.desc()).all()
    
    # Get fund transfers initiated by this chair
    transfers = FundTransfer.query.filter_by(from_user_id=current_user.id).order_by(FundTransfer.created_at.desc()).all()
    
    # Calculate statistics
    total_pledged = sum(p.amount_pledged for p in pledges)
    total_pledge_collected = sum(p.amount_paid for p in pledges)
    total_scheduled = sum(sp.total_collected for sp in scheduled_payments)
    total_transferred = sum(t.amount for t in transfers if t.status == 'completed')
    pending_transfer = total_pledge_collected + total_scheduled - total_transferred
    
    # Get finance users for transfer
    finance_users = User.query.filter_by(role='finance', is_active=True).all()
    
    return render_template('fund_management/chair_dashboard.html',
                          pledges=pledges,
                          scheduled_payments=scheduled_payments,
                          transfers=transfers,
                          total_pledged=total_pledged,
                          total_pledge_collected=total_pledge_collected,
                          total_scheduled=total_scheduled,
                          total_transferred=total_transferred,
                          pending_transfer=pending_transfer,
                          finance_users=finance_users,
                          event=event)


@bp.route('/finance/dashboard')
@login_required
@role_required('finance', 'admin', 'super_admin')
def finance_dashboard():
    """Dashboard for finance to receive and confirm all funds"""
    event = current_user.get_current_event()
    
    # Get all transfers to finance
    all_transfers = FundTransfer.query.filter_by(
        transfer_stage='chair_to_finance'
    ).order_by(FundTransfer.created_at.desc()).all()
    
    # Pending transfers that need approval
    pending_transfers = [t for t in all_transfers if t.status == 'pending']
    approved_transfers = [t for t in all_transfers if t.status == 'approved']
    completed_transfers = [t for t in all_transfers if t.status == 'completed']
    
    # Calculate statistics
    total_pending = sum(t.amount for t in pending_transfers)
    total_approved = sum(t.amount for t in approved_transfers)
    total_received = sum(t.amount for t in completed_transfers)
    
    # Get all pledges across the system
    all_pledges = Pledge.query.order_by(Pledge.created_at.desc()).limit(50).all()
    total_pledged_system = db.session.query(db.func.sum(Pledge.amount_pledged)).scalar() or 0
    total_collected_system = db.session.query(db.func.sum(Pledge.amount_paid)).scalar() or 0
    
    # Get all chairs
    chairs = User.query.filter_by(role='chair', is_active=True).all()
    
    return render_template('fund_management/finance_dashboard.html',
                          all_transfers=all_transfers,
                          pending_transfers=pending_transfers,
                          approved_transfers=approved_transfers,
                          completed_transfers=completed_transfers,
                          total_pending=total_pending,
                          total_approved=total_approved,
                          total_received=total_received,
                          all_pledges=all_pledges,
                          total_pledged_system=total_pledged_system,
                          total_collected_system=total_collected_system,
                          chairs=chairs,
                          event=event)


# ============== PLEDGES ==============

@bp.route('/pledges')
@login_required
def list_pledges():
    """List all pledges for the current user"""
    if current_user.role in ['admin', 'super_admin', 'finance']:
        pledges = Pledge.query.order_by(Pledge.created_at.desc()).all()
    else:
        pledges = Pledge.query.filter_by(recorded_by=current_user.id).order_by(Pledge.created_at.desc()).all()
    
    return render_template('fund_management/pledges_list.html', pledges=pledges)


@bp.route('/pledges/create', methods=['GET', 'POST'])
@login_required
def create_pledge():
    """Create a new pledge"""
    form = PledgeForm()
    
    # Populate delegate choices
    delegates = Delegate.query.filter_by(registered_by=current_user.id).all()
    form.delegate_id.choices = [(0, 'Not linked to delegate')] + [(d.id, f"{d.name} ({d.ticket_number})") for d in delegates]
    
    if request.method == 'POST':
        # Debug: log form submission
        print(f"POST received. Form data: {request.form}")
        print(f"Form validates: {form.validate()}")
        if form.errors:
            print(f"Form errors: {form.errors}")
            # Show form errors as flash messages
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'danger')
        
        if form.validate_on_submit():
            try:
                pledge = Pledge(
                    source_type=form.source_type.data,
                    source_name=form.source_name.data,
                    source_phone=form.source_phone.data,
                    source_email=form.source_email.data,
                    delegate_id=form.delegate_id.data if form.delegate_id.data != 0 else None,
                    amount_pledged=float(form.amount_pledged.data.replace(',', '')),
                    due_date=datetime.strptime(form.due_date.data, '%Y-%m-%d').date() if form.due_date.data else None,
                    local_church=form.local_church.data or current_user.local_church,
                    archdeaconry=form.archdeaconry.data or current_user.archdeaconry,
                    parish=form.parish.data or current_user.parish,
                    description=form.description.data,
                    recorded_by=current_user.id,
                    event_id=current_user.current_event_id
                )
                db.session.add(pledge)
                db.session.commit()
                
                flash(f'Pledge of KSh {pledge.amount_pledged:,.2f} from {pledge.source_name} recorded successfully!', 'success')
                return redirect(url_for('fund_management.view_pledge', pledge_id=pledge.id))
            except Exception as e:
                db.session.rollback()
                print(f"Error creating pledge: {str(e)}")
                import traceback
                traceback.print_exc()
                flash(f'Error recording pledge: {str(e)}', 'danger')
    
    return render_template('fund_management/pledge_form.html', form=form, title='Record New Pledge')


@bp.route('/pledges/<int:pledge_id>')
@login_required
def view_pledge(pledge_id):
    """View pledge details"""
    # Refresh from database to get latest data
    pledge = db.session.get(Pledge, pledge_id)
    if not pledge:
        from flask import abort
        abort(404)
    
    # Check access - chairs can view their own pledges
    allowed_roles = ['admin', 'super_admin', 'finance', 'chair']
    if current_user.role not in allowed_roles and pledge.recorded_by != current_user.id:
        flash('You do not have permission to view this pledge.', 'error')
        return redirect(url_for('fund_management.list_pledges'))
    
    payments = PledgePayment.query.filter_by(pledge_id=pledge_id).order_by(PledgePayment.created_at.desc()).all()
    today = date.today()
    form = EmptyForm()  # For CSRF token in cancel form
    return render_template('fund_management/pledge_view.html', pledge=pledge, payments=payments, today=today, form=form)


@bp.route('/pledges/<int:pledge_id>/payment', methods=['GET', 'POST'])
@login_required
def record_pledge_payment(pledge_id):
    """Record a payment against a pledge"""
    pledge = Pledge.query.get_or_404(pledge_id)
    
    # Check access - chairs can record payments for their own pledges
    allowed_roles = ['admin', 'super_admin', 'finance', 'chair']
    if current_user.role not in allowed_roles and pledge.recorded_by != current_user.id:
        flash('You do not have permission to record payments for this pledge.', 'error')
        return redirect(url_for('fund_management.list_pledges'))
    
    form = PledgePaymentForm()
    
    if request.method == 'POST':
        current_app.logger.info(f'POST request received for pledge {pledge_id}')
        current_app.logger.info(f'Form data: {request.form}')
        
        if form.validate_on_submit():
            try:
                amount_str = form.amount.data.replace(',', '') if form.amount.data else '0'
                amount = float(amount_str)
                
                if amount <= 0:
                    flash('Amount must be greater than zero.', 'error')
                    return render_template('fund_management/pledge_payment_form.html', 
                                          form=form, pledge=pledge, balance=pledge.get_balance())
                
                # Create the payment record
                payment = PledgePayment(
                    pledge_id=pledge.id,
                    amount=amount,
                    payment_method=form.payment_method.data,
                    reference=form.reference.data or '',
                    notes=form.notes.data or ''
                )
                db.session.add(payment)
                
                # Update the pledge amount_paid directly
                current_paid = pledge.amount_paid if pledge.amount_paid else 0
                pledge.amount_paid = current_paid + amount
                
                # Update status
                if pledge.amount_paid >= pledge.amount_pledged:
                    pledge.status = 'fulfilled'
                elif pledge.amount_paid > 0:
                    pledge.status = 'partial'
                
                db.session.commit()
                
                current_app.logger.info(f'Payment recorded: {amount}, Total: {pledge.amount_paid}')
                flash(f'Payment of KSh {amount:,.2f} recorded successfully! Total paid: KSh {pledge.amount_paid:,.2f}', 'success')
                return redirect(url_for('fund_management.view_pledge', pledge_id=pledge.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Error recording payment: {str(e)}')
                flash(f'Error recording payment: {str(e)}', 'error')
                return render_template('fund_management/pledge_payment_form.html', 
                                      form=form, pledge=pledge, balance=pledge.get_balance())
        else:
            current_app.logger.error(f'Form validation failed: {form.errors}')
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{field}: {error}', 'error')
    
    return render_template('fund_management/pledge_payment_form.html', 
                          form=form, 
                          pledge=pledge,
                          balance=pledge.get_balance())


@bp.route('/pledges/<int:pledge_id>/cancel', methods=['POST'])
@login_required
def cancel_pledge(pledge_id):
    """Cancel a pledge"""
    pledge = Pledge.query.get_or_404(pledge_id)
    
    # Chairs can cancel their own pledges that have no payments
    allowed_roles = ['admin', 'super_admin', 'chair']
    if current_user.role not in allowed_roles and pledge.recorded_by != current_user.id:
        flash('You do not have permission to cancel this pledge.', 'error')
        return redirect(url_for('fund_management.list_pledges'))
    
    if pledge.amount_paid > 0:
        flash('Cannot cancel a pledge with payments. Contact admin.', 'error')
        return redirect(url_for('fund_management.view_pledge', pledge_id=pledge.id))
    
    pledge.status = 'cancelled'
    db.session.commit()
    flash('Pledge cancelled successfully.', 'success')
    return redirect(url_for('fund_management.list_pledges'))


@bp.route('/pledges/<int:pledge_id>/delete', methods=['POST'])
@login_required
def delete_pledge(pledge_id):
    """Delete a pledge permanently"""
    pledge = Pledge.query.get_or_404(pledge_id)
    
    # Only admins can delete, or chairs can delete their own pledges with no payments
    if current_user.role in ['admin', 'super_admin']:
        # Admins can delete any pledge
        pass
    elif pledge.recorded_by == current_user.id and pledge.amount_paid == 0:
        # Chairs can delete their own pledges with no payments
        pass
    else:
        flash('You do not have permission to delete this pledge.', 'error')
        return redirect(url_for('fund_management.list_pledges'))
    
    # If pledge has payments, delete them first (only if admin)
    if pledge.amount_paid > 0 and current_user.role not in ['admin', 'super_admin']:
        flash('Cannot delete a pledge with payments. Contact admin.', 'error')
        return redirect(url_for('fund_management.view_pledge', pledge_id=pledge.id))
    
    # Delete associated payments first
    PledgePayment.query.filter_by(pledge_id=pledge.id).delete()
    
    # Delete the pledge
    pledge_name = pledge.source_name
    db.session.delete(pledge)
    db.session.commit()
    
    flash(f'Pledge from "{pledge_name}" has been deleted.', 'success')
    return redirect(url_for('fund_management.list_pledges'))


# ============== SCHEDULED PAYMENTS ==============

@bp.route('/scheduled')
@login_required
def list_scheduled_payments():
    """List all scheduled payments"""
    if current_user.role in ['admin', 'super_admin', 'finance']:
        payments = ScheduledPayment.query.order_by(ScheduledPayment.created_at.desc()).all()
    else:
        payments = ScheduledPayment.query.filter_by(recorded_by=current_user.id).order_by(ScheduledPayment.created_at.desc()).all()
    
    return render_template('fund_management/scheduled_list.html', payments=payments)


@bp.route('/scheduled/create', methods=['GET', 'POST'])
@login_required
def create_scheduled_payment():
    """Create a new scheduled payment"""
    form = ScheduledPaymentForm()
    
    # Populate delegate choices
    delegates = Delegate.query.filter_by(registered_by=current_user.id).all()
    form.delegate_id.choices = [(0, 'Not linked to delegate')] + [(d.id, f"{d.name} ({d.ticket_number})") for d in delegates]
    
    if form.validate_on_submit():
        try:
            start_date = datetime.strptime(form.start_date.data, '%Y-%m-%d').date()
            end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d').date() if form.end_date.data else None
            
            scheduled = ScheduledPayment(
                source_type=form.source_type.data,
                source_name=form.source_name.data,
                source_phone=form.source_phone.data,
                source_email=form.source_email.data,
                delegate_id=form.delegate_id.data if form.delegate_id.data != 0 else None,
                amount=float(form.amount.data.replace(',', '')),
                frequency=form.frequency.data,
                start_date=start_date,
                end_date=end_date,
                next_payment_date=start_date,
                local_church=form.local_church.data or current_user.local_church,
                archdeaconry=form.archdeaconry.data or current_user.archdeaconry,
                parish=form.parish.data or current_user.parish,
                description=form.description.data,
                recorded_by=current_user.id,
                event_id=current_user.current_event_id
            )
            
            # Calculate total expected
            if form.frequency.data == 'once':
                scheduled.total_expected = scheduled.amount
            elif end_date:
                # Calculate number of payments
                from dateutil.relativedelta import relativedelta
                num_payments = 0
                current_date = start_date
                while current_date <= end_date:
                    num_payments += 1
                    if form.frequency.data == 'weekly':
                        current_date += relativedelta(weeks=1)
                    elif form.frequency.data == 'monthly':
                        current_date += relativedelta(months=1)
                scheduled.total_expected = scheduled.amount * num_payments
            
            # Create first installment
            first_installment = ScheduledPaymentInstallment(
                due_date=start_date,
                amount_due=scheduled.amount
            )
            scheduled.installments.append(first_installment)
            
            db.session.add(scheduled)
            db.session.commit()
            
            flash(f'Scheduled payment of KSh {scheduled.amount:,.2f} ({scheduled.frequency}) created!', 'success')
            return redirect(url_for('fund_management.view_scheduled_payment', payment_id=scheduled.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating scheduled payment: {str(e)}', 'error')
    
    return render_template('fund_management/scheduled_form.html', form=form, title='Create Scheduled Payment')


@bp.route('/scheduled/<int:payment_id>')
@login_required
def view_scheduled_payment(payment_id):
    """View scheduled payment details"""
    payment = ScheduledPayment.query.get_or_404(payment_id)
    
    if current_user.role not in ['admin', 'super_admin', 'finance'] and payment.recorded_by != current_user.id:
        flash('You do not have permission to view this scheduled payment.', 'error')
        return redirect(url_for('fund_management.list_scheduled_payments'))
    
    installments = payment.installments.order_by(ScheduledPaymentInstallment.due_date).all()
    return render_template('fund_management/scheduled_view.html', payment=payment, installments=installments)


@bp.route('/scheduled/<int:payment_id>/installment/<int:installment_id>/pay', methods=['GET', 'POST'])
@login_required
def pay_installment(payment_id, installment_id):
    """Record payment for an installment"""
    payment = ScheduledPayment.query.get_or_404(payment_id)
    installment = ScheduledPaymentInstallment.query.get_or_404(installment_id)
    
    if installment.scheduled_payment_id != payment_id:
        flash('Invalid installment.', 'error')
        return redirect(url_for('fund_management.view_scheduled_payment', payment_id=payment_id))
    
    form = InstallmentPaymentForm()
    
    if form.validate_on_submit():
        try:
            amount = float(form.amount_paid.data.replace(',', ''))
            installment.amount_paid = amount
            installment.payment_method = form.payment_method.data
            installment.reference = form.reference.data
            installment.paid_at = datetime.utcnow()
            installment.status = 'paid' if amount >= installment.amount_due else 'partial'
            
            # Update parent scheduled payment
            payment.total_collected += amount
            
            # Generate next installment if applicable
            if payment.frequency != 'once' and (not payment.end_date or payment.next_payment_date <= payment.end_date):
                new_due_date = payment.calculate_next_payment_date()
                if new_due_date and (not payment.end_date or new_due_date <= payment.end_date):
                    new_installment = ScheduledPaymentInstallment(
                        scheduled_payment_id=payment.id,
                        due_date=new_due_date,
                        amount_due=payment.amount
                    )
                    db.session.add(new_installment)
                    payment.next_payment_date = new_due_date
            
            db.session.commit()
            flash(f'Payment of KSh {amount:,.2f} recorded!', 'success')
            return redirect(url_for('fund_management.view_scheduled_payment', payment_id=payment_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')
    
    return render_template('fund_management/installment_payment_form.html',
                          form=form,
                          payment=payment,
                          installment=installment)


# ============== FUND TRANSFERS ==============

@bp.route('/transfers')
@login_required
def list_transfers():
    """List fund transfers"""
    if current_user.role in ['admin', 'super_admin', 'finance']:
        transfers = FundTransfer.query.order_by(FundTransfer.created_at.desc()).all()
    else:
        transfers = FundTransfer.query.filter_by(from_user_id=current_user.id).order_by(FundTransfer.created_at.desc()).all()
    
    return render_template('fund_management/transfers_list.html', transfers=transfers)


@bp.route('/transfers/create', methods=['GET', 'POST'])
@login_required
def create_transfer():
    """Create a new fund transfer"""
    form = FundTransferForm()
    
    # Determine recipient options based on role
    if current_user.role == 'chair':
        # Chairs transfer directly to finance (via paybill or bank)
        finance_recipients = User.query.filter(
            User.role.in_(['finance', 'admin', 'super_admin']),
            User.is_active == True
        ).all()
        recipients = finance_recipients
        transfer_stage = 'chair_to_finance'
        to_role = 'finance'
    else:
        flash('Your role cannot initiate fund transfers.', 'error')
        return redirect(url_for('fund_management.dashboard'))
    
    form.to_user_id.choices = [(0, 'Select Recipient')] + [(u.id, f"{u.name} ({u.role})") for u in recipients]
    
    if request.method == 'POST' and form.validate_on_submit():
        if form.to_user_id.data == 0:
            flash('Please select a recipient.', 'error')
        else:
            try:
                amount = float(form.amount.data.replace(',', '')) if form.amount.data else 0
                if amount <= 0:
                    flash('Amount must be greater than zero.', 'error')
                else:
                    # Determine transfer stage and validate payment method
                    payment_method = form.payment_method.data if hasattr(form, 'payment_method') else 'cash'
                    mpesa_reference = form.mpesa_reference.data if hasattr(form, 'mpesa_reference') else None
                    
                    # Get the recipient to determine the correct transfer stage
                    recipient = User.query.get(form.to_user_id.data)
                    if recipient:
                        # Chair paying directly to finance (via paybill or bank)
                        transfer_stage = 'chair_to_finance'
                        to_role = 'finance'
                    
                    # Validate M-Pesa reference if payment method is paybill
                    if payment_method == 'mpesa_paybill' and not mpesa_reference:
                        flash('M-Pesa reference is required for paybill payments.', 'error')
                        return render_template('fund_management/transfer_form.html', form=form, title='Initiate Fund Transfer')
                    
                    transfer = FundTransfer(
                        reference_number=FundTransfer.generate_reference(),
                        amount=amount,
                        from_user_id=current_user.id,
                        from_role=current_user.role,
                        to_user_id=form.to_user_id.data,
                        to_role=to_role,
                        transfer_stage=transfer_stage,
                        payment_method=payment_method,
                        mpesa_reference=mpesa_reference,
                        local_church=current_user.local_church,
                        parish=current_user.parish,
                        archdeaconry=current_user.archdeaconry,
                        event_id=current_user.current_event_id,
                        description=form.description.data or '',
                        submitted_at=datetime.utcnow()
                    )
                    db.session.add(transfer)
                    db.session.commit()
                    
                    current_app.logger.info(f'Transfer created: {transfer.reference_number}, Amount: {transfer.amount}, Method: {payment_method}')
                    flash(f'Fund transfer of KSh {transfer.amount:,.2f} submitted! Reference: {transfer.reference_number}', 'success')
                    return redirect(url_for('fund_management.view_transfer', transfer_id=transfer.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Error creating transfer: {str(e)}')
                flash(f'Error creating transfer: {str(e)}', 'error')
    
    return render_template('fund_management/transfer_form.html', form=form, title='Initiate Fund Transfer', is_chair=(current_user.role == 'chair'))


@bp.route('/transfers/<int:transfer_id>')
@login_required
def view_transfer(transfer_id):
    """View fund transfer details"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
    # Check access
    allowed = (
        current_user.role in ['admin', 'super_admin', 'finance'] or
        transfer.from_user_id == current_user.id or
        transfer.to_user_id == current_user.id
    )
    if not allowed:
        flash('You do not have permission to view this transfer.', 'error')
        return redirect(url_for('fund_management.list_transfers'))
    
    approvals = transfer.approvals.order_by(FundTransferApproval.created_at).all()
    return render_template('fund_management/transfer_view.html', transfer=transfer, approvals=approvals)


@bp.route('/transfers/<int:transfer_id>/approve', methods=['GET', 'POST'])
@login_required
def approve_transfer(transfer_id):
    """Approve or reject a fund transfer"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
    # Only recipient or admin can approve
    if transfer.to_user_id != current_user.id and current_user.role not in ['admin', 'super_admin']:
        flash('You do not have permission to approve this transfer.', 'error')
        return redirect(url_for('fund_management.view_transfer', transfer_id=transfer_id))
    
    if transfer.status != 'pending':
        flash('This transfer has already been processed.', 'error')
        return redirect(url_for('fund_management.view_transfer', transfer_id=transfer_id))
    
    form = FundTransferApprovalForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            if form.action.data == 'approve':
                # Create approval record
                approval = FundTransferApproval(
                    transfer_id=transfer.id,
                    approved_by=current_user.id,
                    action='approved',
                    notes=form.notes.data or ''
                )
                transfer.status = 'approved'
                transfer.approved_at = datetime.utcnow()
                db.session.add(approval)
                db.session.commit()
                flash(f'Transfer {transfer.reference_number} approved!', 'success')
            else:
                # Create rejection record
                approval = FundTransferApproval(
                    transfer_id=transfer.id,
                    approved_by=current_user.id,
                    action='rejected',
                    notes=form.notes.data or ''
                )
                transfer.status = 'rejected'
                db.session.add(approval)
                db.session.commit()
                flash(f'Transfer {transfer.reference_number} rejected.', 'warning')
            
            return redirect(url_for('fund_management.view_transfer', transfer_id=transfer_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error processing transfer: {str(e)}')
            flash(f'Error processing transfer: {str(e)}', 'error')
    
    return render_template('fund_management/transfer_approve_form.html', form=form, transfer=transfer)


@bp.route('/transfers/<int:transfer_id>/complete', methods=['GET', 'POST'])
@login_required
@role_required('finance', 'admin', 'super_admin')
def complete_transfer(transfer_id):
    """Mark a transfer as completed (funds received)"""
    transfer = FundTransfer.query.get_or_404(transfer_id)
    
    if transfer.status != 'approved':
        flash('Only approved transfers can be completed.', 'error')
        return redirect(url_for('fund_management.view_transfer', transfer_id=transfer_id))
    
    form = FundTransferCompleteForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Create completion record
            approval = FundTransferApproval(
                transfer_id=transfer.id,
                approved_by=current_user.id,
                action='completed',
                notes=form.notes.data or ''
            )
            transfer.status = 'completed'
            transfer.completed_at = datetime.utcnow()
            db.session.add(approval)
            db.session.commit()
            
            flash(f'Transfer {transfer.reference_number} completed! Funds confirmed received.', 'success')
            return redirect(url_for('fund_management.finance_dashboard'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error completing transfer: {str(e)}')
            flash(f'Error completing transfer: {str(e)}', 'error')
    
    return render_template('fund_management/transfer_complete_form.html', form=form, transfer=transfer)


# ============== PAYMENT CONFIRMATION ==============

@bp.route('/payments/pending')
@login_required
def pending_payments():
    """List payments pending confirmation"""
    # Get pledge payments pending confirmation
    pending_pledge_payments = PledgePayment.query.filter_by(status='pending').all()
    
    # Filter based on user role
    if current_user.role not in ['admin', 'super_admin', 'finance']:
        pending_pledge_payments = [p for p in pending_pledge_payments if p.pledge.recorded_by == current_user.id]
    
    return render_template('fund_management/pending_payments.html', 
                          pending_payments=pending_pledge_payments)


@bp.route('/payments/<int:payment_id>/confirm', methods=['GET', 'POST'])
@login_required
@role_required('finance', 'admin', 'super_admin')
def confirm_payment(payment_id):
    """Confirm a pledge payment"""
    payment = PledgePayment.query.get_or_404(payment_id)
    form = PaymentConfirmationForm()
    
    if form.validate_on_submit():
        try:
            if form.action.data == 'confirm':
                payment.status = 'confirmed'
                payment.confirmed_by = current_user.id
                payment.confirmed_at = datetime.utcnow()
                flash('Payment confirmed!', 'success')
            else:
                payment.status = 'rejected'
                payment.confirmed_by = current_user.id
                payment.confirmed_at = datetime.utcnow()
                # Reverse the payment amount on pledge
                payment.pledge.amount_paid -= payment.amount
                payment.pledge.update_status()
                flash('Payment rejected.', 'warning')
            
            db.session.commit()
            return redirect(url_for('fund_management.pending_payments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing payment: {str(e)}', 'error')
    
    return render_template('fund_management/confirm_payment_form.html', 
                          form=form, 
                          payment=payment)


# ============== REPORTS ==============

@bp.route('/reports')
@login_required
def reports():
    """Fund management reports"""
    event = current_user.get_current_event()
    
    # Get summary statistics
    if current_user.role in ['admin', 'super_admin', 'finance']:
        # Full system view
        total_pledged = db.session.query(db.func.sum(Pledge.amount_pledged)).scalar() or 0
        total_collected = db.session.query(db.func.sum(Pledge.amount_paid)).scalar() or 0
        total_scheduled = db.session.query(db.func.sum(ScheduledPayment.total_collected)).scalar() or 0
        total_transferred = db.session.query(
            db.func.sum(FundTransfer.amount)
        ).filter(FundTransfer.status == 'completed', FundTransfer.transfer_stage == 'chair_to_finance').scalar() or 0
        
        # By archdeaconry
        by_archdeaconry = db.session.query(
            Pledge.archdeaconry,
            db.func.sum(Pledge.amount_pledged).label('pledged'),
            db.func.sum(Pledge.amount_paid).label('collected')
        ).group_by(Pledge.archdeaconry).all()
        
        # By source type
        by_source = db.session.query(
            Pledge.source_type,
            db.func.sum(Pledge.amount_pledged).label('pledged'),
            db.func.sum(Pledge.amount_paid).label('collected')
        ).group_by(Pledge.source_type).all()
    else:
        # User's own data
        user_pledges = Pledge.query.filter_by(recorded_by=current_user.id).all()
        total_pledged = sum(p.amount_pledged for p in user_pledges)
        total_collected = sum(p.amount_paid for p in user_pledges)
        
        user_scheduled = ScheduledPayment.query.filter_by(recorded_by=current_user.id).all()
        total_scheduled = sum(sp.total_collected for sp in user_scheduled)
        
        user_transfers = FundTransfer.query.filter_by(from_user_id=current_user.id, status='completed').all()
        total_transferred = sum(t.amount for t in user_transfers)
        
        by_archdeaconry = []
        by_source = []
    
    return render_template('fund_management/reports.html',
                          total_pledged=total_pledged,
                          total_collected=total_collected,
                          total_scheduled=total_scheduled,
                          total_transferred=total_transferred,
                          by_archdeaconry=by_archdeaconry,
                          by_source=by_source,
                          event=event)


# ============== API ENDPOINTS ==============

@bp.route('/api/pledges/<int:pledge_id>/status')
@login_required
def api_pledge_status(pledge_id):
    """Get pledge status via API"""
    pledge = Pledge.query.get_or_404(pledge_id)
    return jsonify({
        'id': pledge.id,
        'amount_pledged': pledge.amount_pledged,
        'amount_paid': pledge.amount_paid,
        'balance': pledge.get_balance(),
        'status': pledge.status
    })


@bp.route('/api/transfers/stats')
@login_required
def api_transfer_stats():
    """Get transfer statistics"""
    if current_user.role in ['admin', 'super_admin', 'finance']:
        pending = FundTransfer.query.filter_by(status='pending').count()
        approved = FundTransfer.query.filter_by(status='approved').count()
        completed = FundTransfer.query.filter_by(status='completed').count()
        
        total_pending = db.session.query(
            db.func.sum(FundTransfer.amount)
        ).filter(FundTransfer.status == 'pending').scalar() or 0
        
        total_completed = db.session.query(
            db.func.sum(FundTransfer.amount)
        ).filter(FundTransfer.status == 'completed').scalar() or 0
    else:
        pending = FundTransfer.query.filter_by(from_user_id=current_user.id, status='pending').count()
        approved = FundTransfer.query.filter_by(from_user_id=current_user.id, status='approved').count()
        completed = FundTransfer.query.filter_by(from_user_id=current_user.id, status='completed').count()
        total_pending = 0
        total_completed = 0
    
    return jsonify({
        'pending_count': pending,
        'approved_count': approved,
        'completed_count': completed,
        'total_pending_amount': total_pending,
        'total_completed_amount': total_completed
    })
