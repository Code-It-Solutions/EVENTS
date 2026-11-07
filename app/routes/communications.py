from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from app import db
from app.models.delegate import Delegate
from app.models.event import Event
from app.models.operations import Announcement, PaymentReminder
from app.utils.sms import (
    SMSService, WhatsAppService, AnnouncementService, 
    AutomatedReminderService, ThankYouService
)

communications_bp = Blueprint('communications', __name__, url_prefix='/communications')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@communications_bp.route('/')
@login_required
@admin_required
def index():
    """Communications dashboard"""
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(10).all()
    reminders = PaymentReminder.query.order_by(PaymentReminder.sent_at.desc()).limit(10).all()
    
    # Get stats
    stats = {
        'total_announcements': Announcement.query.count(),
        'pending_announcements': Announcement.query.filter_by(status='scheduled').count(),
        'sent_announcements': Announcement.query.filter_by(status='sent').count(),
        'total_reminders': PaymentReminder.query.count()
    }
    
    return render_template('communications/index.html',
        announcements=announcements,
        reminders=reminders,
        stats=stats
    )


@communications_bp.route('/announcements')
@login_required
@admin_required
def list_announcements():
    """List all announcements"""
    status = request.args.get('status', '')
    
    query = Announcement.query
    if status:
        query = query.filter_by(status=status)
    
    announcements = query.order_by(Announcement.created_at.desc()).all()
    
    return render_template('communications/announcements.html',
        announcements=announcements,
        current_status=status
    )


@communications_bp.route('/announcements/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_announcement():
    """Create a new announcement"""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        channels = request.form.getlist('channels')
        target_group = request.form.get('target_group', 'all')
        event_id = request.form.get('event_id', type=int)
        scheduled_for = request.form.get('scheduled_for')
        
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('communications.create_announcement'))
        
        scheduled_datetime = None
        if scheduled_for:
            try:
                scheduled_datetime = datetime.fromisoformat(scheduled_for)
            except ValueError:
                flash('Invalid scheduled date format.', 'danger')
                return redirect(url_for('communications.create_announcement'))
        
        announcement = AnnouncementService.create_announcement(
            title=title,
            content=content,
            channels=channels,
            target_group=target_group,
            event_id=event_id,
            created_by=current_user.id,
            scheduled_for=scheduled_datetime
        )
        
        # Log activity
        current_user.log_activity(
            'create_announcement',
            'announcement',
            announcement.id,
            new_values={'title': title, 'channels': channels, 'target': target_group}
        )
        
        flash('Announcement created successfully!', 'success')
        return redirect(url_for('communications.list_announcements'))
    
    events = Event.query.filter_by(is_active=True).all()
    return render_template('communications/create_announcement.html', events=events)


@communications_bp.route('/announcements/<int:announcement_id>/send', methods=['POST'])
@login_required
@admin_required
def send_announcement(announcement_id):
    """Send an announcement immediately"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    # Initialize SMS service (in production, use real credentials)
    sms_service = SMSService()
    
    results = AnnouncementService.send_announcement(announcement_id, sms_service)
    
    # Log activity
    current_user.log_activity(
        'send_announcement',
        'announcement',
        announcement_id,
        new_values={'recipients': results.get('total_recipients', 0)}
    )
    
    flash(f'Announcement sent to {results["total_recipients"]} recipients!', 'success')
    return redirect(url_for('communications.list_announcements'))


@communications_bp.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    """Delete an announcement"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    db.session.delete(announcement)
    db.session.commit()
    
    flash('Announcement deleted.', 'success')
    return redirect(url_for('communications.list_announcements'))


@communications_bp.route('/bulk-sms', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_sms():
    """Send bulk SMS to delegates"""
    if request.method == 'POST':
        message = request.form.get('message')
        target_group = request.form.get('target_group', 'all')
        event_id = request.form.get('event_id', type=int)
        
        if not message:
            flash('Message is required.', 'danger')
            return redirect(url_for('communications.bulk_sms'))
        
        # Get target delegates
        query = Delegate.query
        
        if event_id:
            query = query.filter_by(event_id=event_id)
        
        if target_group == 'paid':
            query = query.filter_by(payment_status='paid')
        elif target_group == 'unpaid':
            query = query.filter(Delegate.payment_status.in_(['pending', 'partial']))
        elif target_group == 'checked_in':
            query = query.filter_by(checked_in=True)
        elif target_group == 'not_checked_in':
            query = query.filter_by(checked_in=False)
        
        delegates = query.all()
        
        if not delegates:
            flash('No delegates found matching the criteria.', 'warning')
            return redirect(url_for('communications.bulk_sms'))
        
        # Send SMS
        sms_service = SMSService()
        results = sms_service.send_bulk_sms(delegates, message)
        
        # Log activity
        current_user.log_activity(
            'send_bulk_sms',
            'communication',
            None,
            new_values={
                'target_group': target_group,
                'sent': results['sent'],
                'failed': results['failed']
            }
        )
        
        flash(f'SMS sent successfully! Sent: {results["sent"]}, Failed: {results["failed"]}', 'success')
        return redirect(url_for('communications.bulk_sms'))
    
    # Get delegate counts for preview
    events = Event.query.filter_by(is_active=True).all()
    delegate_counts = {
        'all': Delegate.query.count(),
        'paid': Delegate.query.filter_by(payment_status='paid').count(),
        'unpaid': Delegate.query.filter(Delegate.payment_status.in_(['pending', 'partial'])).count(),
        'checked_in': Delegate.query.filter_by(checked_in=True).count(),
        'not_checked_in': Delegate.query.filter_by(checked_in=False).count()
    }
    
    return render_template('communications/bulk_sms.html',
        events=events,
        delegate_counts=delegate_counts
    )


@communications_bp.route('/payment-reminders')
@login_required
@admin_required
def payment_reminders():
    """View payment reminder history"""
    reminders = PaymentReminder.query.order_by(PaymentReminder.sent_at.desc()).all()
    
    # Get unpaid delegates
    unpaid_delegates = Delegate.query.filter(
        Delegate.payment_status.in_(['pending', 'partial'])
    ).order_by(Delegate.created_at.desc()).all()
    
    unpaid_count = len(unpaid_delegates)
    
    return render_template('communications/payment_reminders.html',
        reminders=reminders,
        unpaid_count=unpaid_count,
        unpaid_delegates=unpaid_delegates
    )


@communications_bp.route('/payment-reminders/send', methods=['POST'])
@login_required
@admin_required
def send_payment_reminders():
    """Send payment reminders to unpaid delegates"""
    event_id = request.form.get('event_id', type=int)
    message_template = request.form.get('message') or (
        "Hello {name}, this is a reminder that your KAYO registration payment is pending. "
        "Please complete your payment to confirm your attendance. Thank you!"
    )
    
    # Get unpaid delegates
    query = Delegate.query.filter(
        Delegate.payment_status.in_(['pending', 'partial'])
    )
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    delegates = query.all()
    
    if not delegates:
        flash('No unpaid delegates found.', 'info')
        return redirect(url_for('communications.payment_reminders'))
    
    # Send reminders
    sms_service = SMSService()
    sent_count = 0
    
    for delegate in delegates:
        # Check if reminder was sent recently (within 24 hours)
        recent_reminder = PaymentReminder.query.filter(
            PaymentReminder.delegate_id == delegate.id,
            PaymentReminder.sent_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).first()
        
        if recent_reminder:
            continue  # Skip if already reminded today
        
        # Personalize and send message
        message = message_template.format(
            name=delegate.name,
            phone=delegate.phone,
            payment_status=delegate.payment_status
        )
        
        result = sms_service.send_sms(delegate.phone, message)
        
        # Record reminder
        reminder = PaymentReminder(
            delegate_id=delegate.id,
            message=message,
            channel='sms',
            status='sent' if result['success'] else 'failed'
        )
        db.session.add(reminder)
        
        if result['success']:
            sent_count += 1
    
    db.session.commit()
    
    # Log activity
    current_user.log_activity(
        'send_payment_reminders',
        'communication',
        None,
        new_values={'sent_count': sent_count, 'total_unpaid': len(delegates)}
    )
    
    flash(f'Payment reminders sent to {sent_count} delegates!', 'success')
    return redirect(url_for('communications.payment_reminders'))


@communications_bp.route('/api/preview-recipients')
@login_required
@admin_required
def preview_recipients():
    """API to preview recipient count based on filters"""
    target_group = request.args.get('target_group', 'all')
    event_id = request.args.get('event_id', type=int)
    
    query = Delegate.query
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    if target_group == 'paid':
        query = query.filter_by(payment_status='paid')
    elif target_group == 'unpaid':
        query = query.filter(Delegate.payment_status.in_(['pending', 'partial']))
    elif target_group == 'checked_in':
        query = query.filter_by(checked_in=True)
    elif target_group == 'not_checked_in':
        query = query.filter_by(checked_in=False)
    
    count = query.count()
    
    return jsonify({'count': count})


# ==================== WHATSAPP ROUTES ====================

@communications_bp.route('/whatsapp', methods=['GET', 'POST'])
@login_required
@admin_required
def whatsapp_messages():
    """Send WhatsApp messages to delegates"""
    if request.method == 'POST':
        message = request.form.get('message')
        target_group = request.form.get('target_group', 'all')
        event_id = request.form.get('event_id', type=int)
        
        if not message:
            flash('Message is required.', 'danger')
            return redirect(url_for('communications.whatsapp_messages'))
        
        # Get target delegates
        query = Delegate.query
        
        if event_id:
            query = query.filter_by(event_id=event_id)
        
        if target_group == 'paid':
            query = query.filter_by(payment_status='paid')
        elif target_group == 'unpaid':
            query = query.filter(Delegate.payment_status.in_(['pending', 'partial']))
        elif target_group == 'checked_in':
            query = query.filter_by(checked_in=True)
        elif target_group == 'not_checked_in':
            query = query.filter_by(checked_in=False)
        
        delegates = query.all()
        
        if not delegates:
            flash('No delegates found matching the criteria.', 'warning')
            return redirect(url_for('communications.whatsapp_messages'))
        
        # Get event for personalization
        event = Event.query.get(event_id) if event_id else None
        
        # Send WhatsApp messages
        whatsapp_service = WhatsAppService()
        results = whatsapp_service.send_bulk_whatsapp(delegates, message, event)
        
        # Log activity
        current_user.log_activity(
            'send_bulk_whatsapp',
            'communication',
            None,
            new_values={
                'target_group': target_group,
                'sent': results['sent'],
                'failed': results['failed']
            }
        )
        
        flash(f'WhatsApp messages sent! Sent: {results["sent"]}, Failed: {results["failed"]}', 'success')
        return redirect(url_for('communications.whatsapp_messages'))
    
    # Get delegate counts for preview
    events = Event.query.filter_by(is_active=True).all()
    delegate_counts = {
        'all': Delegate.query.count(),
        'paid': Delegate.query.filter_by(is_paid=True).count(),
        'unpaid': Delegate.query.filter_by(is_paid=False).count(),
        'checked_in': Delegate.query.filter_by(checked_in=True).count(),
        'not_checked_in': Delegate.query.filter_by(checked_in=False).count()
    }
    
    return render_template('communications/whatsapp.html',
        events=events,
        delegate_counts=delegate_counts
    )


# ==================== AUTOMATED REMINDERS ROUTES ====================

@communications_bp.route('/automated-reminders', methods=['GET', 'POST'])
@login_required
@admin_required
def automated_reminders():
    """Automated payment reminder system"""
    if request.method == 'POST':
        event_id = request.form.get('event_id', type=int)
        reminder_type = request.form.get('reminder_type', 'first_reminder')
        channels = request.form.getlist('channels') or ['sms']
        custom_message = request.form.get('custom_message')
        
        # Send reminders
        results = AutomatedReminderService.send_payment_reminders(
            event_id=event_id,
            reminder_type=reminder_type,
            channels=channels,
            custom_message=custom_message if custom_message and custom_message.strip() else None
        )
        
        # Log activity
        current_user.log_activity(
            'send_automated_reminders',
            'communication',
            None,
            new_values={
                'reminder_type': reminder_type,
                'channels': channels,
                'sms_sent': results.get('sms_sent', 0),
                'whatsapp_sent': results.get('whatsapp_sent', 0),
                'skipped': results.get('skipped', 0)
            }
        )
        
        flash(
            f'Reminders sent! SMS: {results.get("sms_sent", 0)}, '
            f'WhatsApp: {results.get("whatsapp_sent", 0)}, '
            f'Skipped (recent reminder): {results.get("skipped", 0)}',
            'success'
        )
        return redirect(url_for('communications.automated_reminders'))
    
    # Get data for the form
    events = Event.query.filter_by(is_active=True).all()
    reminder_templates = AutomatedReminderService.get_reminder_templates()
    
    # Get unpaid delegate counts by event
    unpaid_counts = {}
    for event in events:
        unpaid_counts[event.id] = Delegate.query.filter(
            Delegate.event_id == event.id,
            Delegate.payment_status.in_(['pending', 'partial'])
        ).count()
    
    total_unpaid = Delegate.query.filter(
        Delegate.payment_status.in_(['pending', 'partial'])
    ).count()
    
    # Get recent reminders
    recent_reminders = PaymentReminder.query.order_by(
        PaymentReminder.sent_at.desc()
    ).limit(20).all()
    
    return render_template('communications/automated_reminders.html',
        events=events,
        reminder_templates=reminder_templates,
        unpaid_counts=unpaid_counts,
        total_unpaid=total_unpaid,
        recent_reminders=recent_reminders
    )


# ==================== THANK YOU MESSAGES ROUTES ====================

@communications_bp.route('/thank-you', methods=['GET', 'POST'])
@login_required
@admin_required
def thank_you_messages():
    """Send post-event thank-you messages"""
    if request.method == 'POST':
        event_id = request.form.get('event_id', type=int)
        template_type = request.form.get('template_type', 'general')
        channels = request.form.getlist('channels') or ['sms']
        target_group = request.form.get('target_group', 'checked_in')
        custom_message = request.form.get('custom_message')
        
        if not event_id:
            flash('Please select an event.', 'danger')
            return redirect(url_for('communications.thank_you_messages'))
        
        # Send thank-you messages
        results = ThankYouService.send_thank_you_messages(
            event_id=event_id,
            template_type=template_type,
            channels=channels,
            target_group=target_group,
            custom_message=custom_message if custom_message and custom_message.strip() else None
        )
        
        if not results.get('success', True):
            flash(f'Error: {results.get("error", "Unknown error")}', 'danger')
            return redirect(url_for('communications.thank_you_messages'))
        
        # Log activity
        current_user.log_activity(
            'send_thank_you_messages',
            'communication',
            event_id,
            new_values={
                'template_type': template_type,
                'channels': channels,
                'target_group': target_group,
                'sms_sent': results.get('sms_sent', 0),
                'whatsapp_sent': results.get('whatsapp_sent', 0)
            }
        )
        
        flash(
            f'Thank-you messages sent! SMS: {results.get("sms_sent", 0)}, '
            f'WhatsApp: {results.get("whatsapp_sent", 0)}',
            'success'
        )
        return redirect(url_for('communications.thank_you_messages'))
    
    # Get data for the form
    events = Event.query.all()
    thank_you_templates = ThankYouService.get_thank_you_templates()
    
    # Get delegate counts by event
    delegate_counts = {}
    for event in events:
        delegate_counts[event.id] = {
            'all': Delegate.query.filter_by(event_id=event.id).count(),
            'checked_in': Delegate.query.filter_by(event_id=event.id, checked_in=True).count(),
            'paid': Delegate.query.filter_by(event_id=event.id, payment_status='paid').count()
        }
    
    return render_template('communications/thank_you.html',
        events=events,
        thank_you_templates=thank_you_templates,
        delegate_counts=delegate_counts
    )


# ==================== API ENDPOINTS ====================

@communications_bp.route('/api/reminder-templates')
@login_required
def get_reminder_templates():
    """API to get reminder templates"""
    templates = AutomatedReminderService.get_reminder_templates()
    return jsonify(templates)


@communications_bp.route('/api/thank-you-templates')
@login_required
def get_thank_you_templates():
    """API to get thank-you templates"""
    templates = ThankYouService.get_thank_you_templates()
    return jsonify(templates)


@communications_bp.route('/api/unpaid-count')
@login_required
def get_unpaid_count():
    """API to get unpaid delegate count for an event"""
    event_id = request.args.get('event_id', type=int)
    
    query = Delegate.query.filter(Delegate.payment_status.in_(['pending', 'partial']))
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    count = query.count()
    return jsonify({'count': count})


@communications_bp.route('/api/delegate-counts/<int:event_id>')
@login_required
def get_delegate_counts(event_id):
    """API to get delegate counts for an event"""
    counts = {
        'all': Delegate.query.filter_by(event_id=event_id).count(),
        'checked_in': Delegate.query.filter_by(event_id=event_id, checked_in=True).count(),
        'paid': Delegate.query.filter_by(event_id=event_id, payment_status='paid').count(),
        'unpaid': Delegate.query.filter(
            Delegate.event_id == event_id,
            Delegate.payment_status.in_(['pending', 'partial'])
        ).count()
    }
    return jsonify(counts)
