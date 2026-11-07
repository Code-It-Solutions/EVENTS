"""
Public Registration Routes
Allows delegates to self-register via a public link without logging in.
Registrations require chairperson approval before becoming active delegates.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.delegate import Delegate
from app.models.pending_delegate import PendingDelegate
from app.models.event import Event
from app.models.user import User
from app.church_data import CHURCH_DATA

public_bp = Blueprint('public', __name__, url_prefix='/register')


@public_bp.route('/conference-program')
def conference_program():
    """Public conference program and schedule page"""
    event = Event.query.filter_by(is_active=True).first()
    return render_template('public/conference_program.html', event=event)


@public_bp.route('/')
def register_landing():
    """Landing page for public delegate registration"""
    # Get active event if any
    event = Event.query.filter_by(is_active=True).first()
    return render_template('public/register_landing.html', event=event)


@public_bp.route('/delegate', methods=['GET', 'POST'])
def register_delegate():
    """Public delegate self-registration form"""
    # Get active event
    event = Event.query.filter_by(is_active=True).first()
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        archdeaconry = request.form.get('archdeaconry', '').strip()
        parish = request.form.get('parish', '').strip()
        local_church = request.form.get('local_church', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        id_number = request.form.get('id_number', '').strip()
        email = request.form.get('email', '').strip()
        gender = request.form.get('gender', '').strip()
        age_bracket = request.form.get('age_bracket', '').strip()
        
        # Validation
        errors = []
        if not name:
            errors.append('Full name is required')
        if not archdeaconry:
            errors.append('Archdeaconry is required')
        if not parish:
            errors.append('Parish is required')
        if not local_church:
            errors.append('Local church is required')
        if not gender:
            errors.append('Gender is required')
        if not age_bracket:
            errors.append('Age bracket is required')
        
        # Check for duplicate pending registrations
        if phone_number:
            existing = PendingDelegate.query.filter_by(
                phone_number=phone_number, 
                status='pending'
            ).first()
            if existing:
                errors.append('A registration with this phone number is already pending approval')
        
        if id_number:
            existing = PendingDelegate.query.filter_by(
                id_number=id_number,
                status='pending'
            ).first()
            if existing:
                errors.append('A registration with this ID number is already pending approval')
            
            # Also check existing delegates
            existing_delegate = Delegate.query.filter_by(id_number=id_number).first()
            if existing_delegate:
                errors.append('A delegate with this ID number is already registered')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('public/register_form.html', 
                                 event=event, 
                                 church_data=CHURCH_DATA,
                                 form_data=request.form)
        
        # Create pending registration
        pending = PendingDelegate(
            registration_token=PendingDelegate.generate_token(),
            name=name,
            archdeaconry=archdeaconry,
            parish=parish,
            local_church=local_church,
            phone_number=phone_number or None,
            id_number=id_number or None,
            email=email or None,
            gender=gender,
            age_bracket=age_bracket,
            category='delegate',
            event_id=event.id if event else None,
            status='pending'
        )
        
        db.session.add(pending)
        db.session.commit()
        
        # Redirect to confirmation page
        return redirect(url_for('public.registration_submitted', token=pending.registration_token))
    
    return render_template('public/register_form.html', 
                         event=event, 
                         church_data=CHURCH_DATA,
                         form_data={})


@public_bp.route('/submitted/<token>')
def registration_submitted(token):
    """Confirmation page after registration submission"""
    pending = PendingDelegate.query.filter_by(registration_token=token).first_or_404()
    return render_template('public/registration_submitted.html', pending=pending)


@public_bp.route('/status/<token>')
def registration_status(token):
    """Check registration status"""
    pending = PendingDelegate.query.filter_by(registration_token=token).first_or_404()
    return render_template('public/registration_status.html', pending=pending)


@public_bp.route('/api/parishes/<archdeaconry>')
def get_parishes(archdeaconry):
    """API endpoint to get parishes for an archdeaconry"""
    parishes = CHURCH_DATA.get(archdeaconry, [])
    return jsonify(parishes)


# ==================== CHAIRPERSON APPROVAL ROUTES ====================

@public_bp.route('/approvals')
@login_required
def pending_approvals():
    """View pending registrations for approval (Chairpersons and Admins)"""
    # Check if user can approve (chairs, admins)
    if current_user.role not in ['chair', 'admin', 'super_admin']:
        flash('You do not have permission to view pending approvals.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get pending registrations based on user role
    pending_list = PendingDelegate.get_pending_for_user(current_user)
    
    # All approved users can approve
    can_approve = True
    
    # Get counts
    pending_count = len([p for p in pending_list if p.status == 'pending'])
    
    return render_template('public/pending_approvals.html',
                         pending_list=pending_list,
                         pending_count=pending_count,
                         can_approve=can_approve)


@public_bp.route('/approvals/<int:id>/approve', methods=['POST'])
@login_required
def approve_registration(id):
    """Approve a pending registration"""
    # Check permissions
    if current_user.role not in ['chair', 'admin', 'super_admin']:
        flash('You do not have permission to approve registrations.', 'danger')
        return redirect(url_for('public.pending_approvals'))
    
    pending = PendingDelegate.query.get_or_404(id)
    
    # Verify the chair can approve this registration (flexible matching)
    if current_user.role == 'chair':
        can_approve = False
        # Check if any of the chair's locations match the pending delegate
        if current_user.local_church and current_user.local_church.lower() == pending.local_church.lower():
            can_approve = True
        elif current_user.parish and current_user.parish.lower() == pending.parish.lower():
            can_approve = True
        elif current_user.archdeaconry and current_user.archdeaconry.lower() == pending.archdeaconry.lower():
            can_approve = True
        # If chair has no location set, allow approval (they need to set their profile)
        elif not current_user.local_church and not current_user.parish and not current_user.archdeaconry:
            can_approve = True
            
        if not can_approve:
            flash('You can only approve registrations from your local church, parish, or archdeaconry.', 'danger')
            return redirect(url_for('public.pending_approvals'))
    
    if pending.status != 'pending':
        flash('This registration has already been processed.', 'warning')
        return redirect(url_for('public.pending_approvals'))
    
    # Create the actual delegate
    delegate = Delegate(
        ticket_number=Delegate.generate_ticket_number(),
        name=pending.name,
        local_church=pending.local_church,
        parish=pending.parish,
        archdeaconry=pending.archdeaconry,
        phone_number=pending.phone_number,
        id_number=pending.id_number,
        gender=pending.gender,
        category=pending.category,
        event_id=pending.event_id,
        registered_by=current_user.id  # Chairperson becomes the registerer
    )
    
    db.session.add(delegate)
    
    # Update pending status
    pending.status = 'approved'
    pending.reviewed_at = datetime.utcnow()
    pending.reviewed_by = current_user.id
    pending.reviewer_notes = request.form.get('notes', '')
    pending.delegate_id = delegate.id
    
    db.session.commit()
    
    flash(f'Registration for "{delegate.name}" has been approved! Ticket: {delegate.ticket_number}', 'success')
    return redirect(url_for('public.pending_approvals'))


@public_bp.route('/approvals/<int:id>/reject', methods=['POST'])
@login_required
def reject_registration(id):
    """Reject a pending registration"""
    # Check permissions
    if current_user.role not in ['chair', 'admin', 'super_admin']:
        flash('You do not have permission to reject registrations.', 'danger')
        return redirect(url_for('public.pending_approvals'))
    
    pending = PendingDelegate.query.get_or_404(id)
    
    # Verify the chair can reject this registration
    if current_user.role == 'chair':
        if pending.local_church != current_user.local_church:
            flash('You can only reject registrations from your local church.', 'danger')
            return redirect(url_for('public.pending_approvals'))
    
    if pending.status != 'pending':
        flash('This registration has already been processed.', 'warning')
        return redirect(url_for('public.pending_approvals'))
    
    rejection_reason = request.form.get('rejection_reason', 'No reason provided')
    
    # Update pending status
    pending.status = 'rejected'
    pending.reviewed_at = datetime.utcnow()
    pending.reviewed_by = current_user.id
    pending.rejection_reason = rejection_reason
    
    db.session.commit()
    
    flash(f'Registration for "{pending.name}" has been rejected.', 'info')
    return redirect(url_for('public.pending_approvals'))


@public_bp.route('/approvals/<int:id>/view')
@login_required
def view_pending_registration(id):
    """View details of a pending registration"""
    if current_user.role not in ['chair', 'admin', 'super_admin']:
        flash('You do not have permission to view this.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    pending = PendingDelegate.query.get_or_404(id)
    
    # Verify access
    if current_user.role == 'chair':
        if pending.local_church != current_user.local_church:
            flash('You can only view registrations from your local church.', 'danger')
            return redirect(url_for('public.pending_approvals'))
    
    can_approve = True
    
    return render_template('public/view_pending.html', 
                         pending=pending,
                         can_approve=can_approve)
