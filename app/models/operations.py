from datetime import datetime
from app import db


class CheckInRecord(db.Model):
    """Track multi-day check-ins for delegates"""
    __tablename__ = 'check_in_records'
    
    id = db.Column(db.Integer, primary_key=True)
    delegate_id = db.Column(db.Integer, db.ForeignKey('delegates.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    
    # Which day of the event
    check_in_date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Who performed the check-in
    checked_in_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Session tracking (optional)
    session_name = db.Column(db.String(100), nullable=True)  # e.g., "Morning Session", "Workshop A"
    
    # Method
    check_in_method = db.Column(db.String(20), default='manual')  # qr_scan, manual, bulk
    
    def __repr__(self):
        return f'<CheckInRecord Delegate {self.delegate_id} on {self.check_in_date}>'
    
    @staticmethod
    def check_in_delegate(delegate_id, event_id, user_id=None, session_name=None, method='manual'):
        """Record a check-in for a delegate"""
        today = datetime.utcnow().date()
        
        # Check if already checked in today
        existing = CheckInRecord.query.filter_by(
            delegate_id=delegate_id,
            event_id=event_id,
            check_in_date=today
        )
        if session_name:
            existing = existing.filter_by(session_name=session_name)
        
        if existing.first():
            return None, "Already checked in"
        
        record = CheckInRecord(
            delegate_id=delegate_id,
            event_id=event_id,
            check_in_date=today,
            checked_in_by=user_id,
            session_name=session_name,
            check_in_method=method
        )
        db.session.add(record)
        return record, "Check-in successful"
    
    @staticmethod
    def get_daily_attendance(event_id, date=None):
        """Get attendance count for a specific day"""
        if date is None:
            date = datetime.utcnow().date()
        return CheckInRecord.query.filter_by(
            event_id=event_id,
            check_in_date=date
        ).count()
    
    @staticmethod
    def get_delegate_attendance(delegate_id, event_id):
        """Get all check-in records for a delegate"""
        return CheckInRecord.query.filter_by(
            delegate_id=delegate_id,
            event_id=event_id
        ).order_by(CheckInRecord.check_in_date).all()


class Announcement(db.Model):
    """Announcements and bulk messages"""
    __tablename__ = 'announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Message type
    message_type = db.Column(db.String(20), default='general')  # general, reminder, urgent, venue_change
    
    # Delivery channels
    send_sms = db.Column(db.Boolean, default=False)
    send_email = db.Column(db.Boolean, default=False)
    send_whatsapp = db.Column(db.Boolean, default=False)
    
    # Target audience
    target_audience = db.Column(db.String(50), default='all')  # all, paid, unpaid, checked_in, not_checked_in
    target_categories = db.Column(db.Text, default='[]')  # JSON array
    target_archdeaconries = db.Column(db.Text, default='[]')  # JSON array
    
    # Scheduling
    scheduled_for = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, sending, sent, failed
    recipients_count = db.Column(db.Integer, default=0)
    delivered_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Announcement {self.title}>'


class PaymentReminder(db.Model):
    """Track payment reminders sent to delegates"""
    __tablename__ = 'payment_reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    delegate_id = db.Column(db.Integer, db.ForeignKey('delegates.id'), nullable=False)
    
    # Reminder details
    reminder_number = db.Column(db.Integer, default=1)  # 1st, 2nd, 3rd reminder
    reminder_type = db.Column(db.String(50), default='first_reminder')  # first_reminder, second_reminder, final_reminder
    channel = db.Column(db.String(20), default='sms')  # sms, whatsapp, email
    sent_via = db.Column(db.String(20), default='sms')  # sms, email, whatsapp (legacy)
    message = db.Column(db.Text, nullable=True)  # Actual message sent
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # STK push retry
    stk_push_sent = db.Column(db.Boolean, default=False)
    stk_push_response = db.Column(db.Text, nullable=True)
    
    # Status
    status = db.Column(db.String(20), default='sent')  # sent, delivered, failed
    delivered = db.Column(db.Boolean, default=False)
    resulted_in_payment = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<PaymentReminder {self.reminder_number} for Delegate {self.delegate_id}>'
    
    @staticmethod
    def get_reminder_count(delegate_id):
        """Get number of reminders sent to a delegate"""
        return PaymentReminder.query.filter_by(delegate_id=delegate_id).count()
    
    @staticmethod
    def should_send_reminder(delegate_id, max_reminders=3, hours_between=24):
        """Check if a reminder should be sent"""
        from datetime import timedelta
        
        count = PaymentReminder.get_reminder_count(delegate_id)
        if count >= max_reminders:
            return False, "Maximum reminders reached"
        
        last_reminder = PaymentReminder.query.filter_by(
            delegate_id=delegate_id
        ).order_by(PaymentReminder.sent_at.desc()).first()
        
        if last_reminder:
            time_since = datetime.utcnow() - last_reminder.sent_at
            if time_since < timedelta(hours=hours_between):
                return False, f"Last reminder sent {time_since.seconds // 3600} hours ago"
        
        return True, "Reminder can be sent"


class PaymentDiscrepancy(db.Model):
    """Track payment amount discrepancies"""
    __tablename__ = 'payment_discrepancies'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    
    expected_amount = db.Column(db.Float, nullable=False)
    actual_amount = db.Column(db.Float, nullable=False)
    difference = db.Column(db.Float, nullable=False)
    
    # Type
    discrepancy_type = db.Column(db.String(20), nullable=False)  # underpayment, overpayment
    
    # Resolution
    status = db.Column(db.String(20), default='pending')  # pending, resolved, refunded, waived
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentDiscrepancy {self.discrepancy_type}: {self.difference}>'
    
    @staticmethod
    def check_payment_amount(payment, expected_amount):
        """Check if payment amount matches expected and create discrepancy if not"""
        if payment.amount == expected_amount:
            return None
        
        discrepancy = PaymentDiscrepancy(
            payment_id=payment.id,
            expected_amount=expected_amount,
            actual_amount=payment.amount,
            difference=payment.amount - expected_amount,
            discrepancy_type='overpayment' if payment.amount > expected_amount else 'underpayment'
        )
        db.session.add(discrepancy)
        return discrepancy
