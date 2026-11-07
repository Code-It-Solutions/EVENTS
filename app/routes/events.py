from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Event, PricingTier, AuditLog, Role, User, Delegate

events_bp = Blueprint('events', __name__, url_prefix='/events')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@events_bp.route('/')
@login_required
@admin_required
def list_events():
    """List all events"""
    events = Event.query.order_by(Event.start_date.desc()).all()
    return render_template('events/list.html', events=events)


@events_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_event():
    """Create a new event"""
    if request.method == 'POST':
        event = Event(
            name=request.form.get('name'),
            slug=request.form.get('slug', '').lower().replace(' ', '-'),
            description=request.form.get('description'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date(),
            venue=request.form.get('venue'),
            venue_address=request.form.get('venue_address'),
            max_delegates=request.form.get('max_delegates', type=int),
            primary_color=request.form.get('primary_color', '#4e73df'),
            secondary_color=request.form.get('secondary_color', '#858796'),
            is_active=True,
            is_published=request.form.get('is_published') == 'on',
            created_by=current_user.id
        )
        
        # Registration deadline
        deadline = request.form.get('registration_deadline')
        if deadline:
            event.registration_deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
        
        db.session.add(event)
        db.session.commit()
        
        # Log the action
        current_user.log_activity('create', 'event', event.id, f'Created event: {event.name}')
        db.session.commit()
        
        flash(f'Event "{event.name}" created successfully!', 'success')
        return redirect(url_for('events.edit_event', event_id=event.id))
    
    return render_template('events/create.html')


@events_bp.route('/<int:event_id>')
@login_required
@admin_required
def view_event(event_id):
    """View event details"""
    event = Event.query.get_or_404(event_id)
    delegate_count = event.get_delegate_count()
    paid_count = event.get_paid_delegate_count()
    checked_in_count = event.get_checked_in_count()
    
    return render_template('events/view.html',
        event=event,
        delegate_count=delegate_count,
        paid_count=paid_count,
        checked_in_count=checked_in_count
    )


@events_bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_event(event_id):
    """Edit event"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        # Store old values for audit
        old_values = {
            'name': event.name,
            'start_date': str(event.start_date),
            'end_date': str(event.end_date)
        }
        
        event.name = request.form.get('name')
        event.slug = request.form.get('slug', '').lower().replace(' ', '-')
        event.description = request.form.get('description')
        event.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        event.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        event.venue = request.form.get('venue')
        event.venue_address = request.form.get('venue_address')
        event.max_delegates = request.form.get('max_delegates', type=int)
        event.primary_color = request.form.get('primary_color', '#4e73df')
        event.secondary_color = request.form.get('secondary_color', '#858796')
        event.is_published = request.form.get('is_published') == 'on'
        
        deadline = request.form.get('registration_deadline')
        if deadline:
            event.registration_deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M')
        
        # Log the action
        new_values = {
            'name': event.name,
            'start_date': str(event.start_date),
            'end_date': str(event.end_date)
        }
        current_user.log_activity('update', 'event', event.id, 
                                 f'Updated event: {event.name}',
                                 old_values, new_values)
        
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events.view_event', event_id=event.id))
    
    return render_template('events/edit.html', event=event)


@events_bp.route('/<int:event_id>/pricing', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_pricing(event_id):
    """Manage pricing tiers for an event"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            tier = PricingTier(
                event_id=event.id,
                name=request.form.get('name'),
                description=request.form.get('description'),
                price=float(request.form.get('price', 0)),
                max_tickets=request.form.get('max_tickets', type=int),
                group_min_size=request.form.get('group_min_size', type=int),
                group_discount_percent=request.form.get('group_discount_percent', type=float),
                is_active=True
            )
            
            valid_from = request.form.get('valid_from')
            if valid_from:
                tier.valid_from = datetime.strptime(valid_from, '%Y-%m-%dT%H:%M')
            
            valid_until = request.form.get('valid_until')
            if valid_until:
                tier.valid_until = datetime.strptime(valid_until, '%Y-%m-%dT%H:%M')
            
            db.session.add(tier)
            db.session.commit()
            
            current_user.log_activity('create', 'pricing_tier', tier.id,
                                     f'Created pricing tier: {tier.name}')
            db.session.commit()
            
            flash(f'Pricing tier "{tier.name}" created!', 'success')
        
        elif action == 'delete':
            tier_id = request.form.get('tier_id', type=int)
            tier = PricingTier.query.get(tier_id)
            if tier and tier.event_id == event.id:
                current_user.log_activity('delete', 'pricing_tier', tier.id,
                                         f'Deleted pricing tier: {tier.name}')
                db.session.delete(tier)
                db.session.commit()
                flash('Pricing tier deleted!', 'success')
        
        elif action == 'toggle':
            tier_id = request.form.get('tier_id', type=int)
            tier = PricingTier.query.get(tier_id)
            if tier and tier.event_id == event.id:
                tier.is_active = not tier.is_active
                db.session.commit()
                flash(f'Pricing tier {"activated" if tier.is_active else "deactivated"}!', 'success')
        
        return redirect(url_for('events.manage_pricing', event_id=event.id))
    
    tiers = event.pricing_tiers.order_by(PricingTier.price.asc()).all()
    return render_template('events/pricing.html', event=event, tiers=tiers)


@events_bp.route('/switch/<int:event_id>')
@login_required
def switch_event(event_id):
    """Switch to a different event"""
    event = Event.query.get_or_404(event_id)
    if not event.is_active:
        flash('Cannot switch to inactive event.', 'warning')
        return redirect(request.referrer or url_for('events.list_events'))
    
    current_user.current_event_id = event.id
    db.session.commit()
    
    flash(f'Switched to event: {event.name}', 'success')
    return redirect(request.referrer or url_for('admin.dashboard'))


@events_bp.route('/<int:event_id>/custom-fields', methods=['GET', 'POST'])
@login_required
@admin_required
def custom_fields(event_id):
    """Manage custom registration fields"""
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        fields = []
        field_names = request.form.getlist('field_name[]')
        field_types = request.form.getlist('field_type[]')
        field_required = request.form.getlist('field_required[]')
        field_options = request.form.getlist('field_options[]')
        
        for i, name in enumerate(field_names):
            if name.strip():
                field = {
                    'name': name.strip(),
                    'type': field_types[i] if i < len(field_types) else 'text',
                    'required': str(i) in field_required,
                    'options': field_options[i].split(',') if i < len(field_options) and field_options[i] else []
                }
                fields.append(field)
        
        event.set_custom_fields(fields)
        db.session.commit()
        
        flash('Custom fields updated!', 'success')
        return redirect(url_for('events.custom_fields', event_id=event.id))
    
    custom_fields = event.get_custom_fields()
    return render_template('events/custom_fields.html', event=event, custom_fields=custom_fields)
