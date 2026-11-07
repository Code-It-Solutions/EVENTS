"""
Fund Management Models
- Pledges from delegates, well-wishers
- Scheduled payments
- Fund transfers between chairs and finance
"""
from datetime import datetime
from app import db
import json


class Pledge(db.Model):
    """Pledges from delegates, well-wishers, and fundraising"""
    __tablename__ = 'pledges'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Pledge source
    source_type = db.Column(db.String(50), nullable=False)  # delegate, well_wisher, fundraising
    source_name = db.Column(db.String(100), nullable=False)
    source_phone = db.Column(db.String(15), nullable=True)
    source_email = db.Column(db.String(120), nullable=True)
    
    # Link to delegate if applicable
    delegate_id = db.Column(db.Integer, db.ForeignKey('delegates.id'), nullable=True)
    
    # Amount details
    amount_pledged = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, partial, fulfilled, cancelled
    
    # Event context
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Chair who recorded the pledge
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # For tracking church hierarchy
    local_church = db.Column(db.String(100), nullable=True)
    parish = db.Column(db.String(100), nullable=True)
    archdeaconry = db.Column(db.String(100), nullable=True)
    
    # Purpose/description
    description = db.Column(db.Text, nullable=True)
    
    # Due date for the pledge
    due_date = db.Column(db.Date, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    delegate = db.relationship('Delegate', backref='pledges')
    recorder = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_pledges')
    payments = db.relationship('PledgePayment', backref='pledge', lazy='dynamic')
    
    def __repr__(self):
        return f'<Pledge {self.id} - KSh {self.amount_pledged} from {self.source_name}>'
    
    def get_balance(self):
        """Get remaining balance"""
        return self.amount_pledged - (self.amount_paid or 0)
    
    def update_status(self):
        """Update status based on payments"""
        amount_paid = self.amount_paid or 0
        if amount_paid >= self.amount_pledged:
            self.status = 'fulfilled'
        elif amount_paid > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'
    
    def add_payment(self, amount, payment_method, reference=None, notes=None):
        """Record a payment against this pledge"""
        from sqlalchemy.orm.attributes import flag_modified
        
        payment = PledgePayment(
            pledge_id=self.id,
            amount=amount,
            payment_method=payment_method,
            reference=reference,
            notes=notes
        )
        self.amount_paid = (self.amount_paid or 0) + amount
        self.update_status()
        
        # Ensure SQLAlchemy tracks the changes to this pledge
        db.session.add(self)
        db.session.add(payment)
        return payment


class PledgePayment(db.Model):
    """Individual payments against a pledge"""
    __tablename__ = 'pledge_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    pledge_id = db.Column(db.Integer, db.ForeignKey('pledges.id'), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # mpesa, cash, bank_transfer
    reference = db.Column(db.String(100), nullable=True)  # Transaction reference
    notes = db.Column(db.Text, nullable=True)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, rejected
    
    # Confirmation tracking
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    confirmer = db.relationship('User', foreign_keys=[confirmed_by])
    
    def __repr__(self):
        return f'<PledgePayment {self.id} - KSh {self.amount}>'


class ScheduledPayment(db.Model):
    """Scheduled/recurring payments"""
    __tablename__ = 'scheduled_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Source info
    source_type = db.Column(db.String(50), nullable=False)  # delegate, well_wisher, fundraising
    source_name = db.Column(db.String(100), nullable=False)
    source_phone = db.Column(db.String(15), nullable=True)
    source_email = db.Column(db.String(120), nullable=True)
    
    # Link to delegate if applicable
    delegate_id = db.Column(db.Integer, db.ForeignKey('delegates.id'), nullable=True)
    
    # Schedule details
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # once, weekly, monthly
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    next_payment_date = db.Column(db.Date, nullable=True)
    
    # Total expected and collected
    total_expected = db.Column(db.Float, default=0)
    total_collected = db.Column(db.Float, default=0)
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, paused, completed, cancelled
    
    # Event context
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Chair who recorded
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Church hierarchy
    local_church = db.Column(db.String(100), nullable=True)
    parish = db.Column(db.String(100), nullable=True)
    archdeaconry = db.Column(db.String(100), nullable=True)
    
    # Description
    description = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    delegate = db.relationship('Delegate', backref='scheduled_payments')
    recorder = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_scheduled_payments')
    installments = db.relationship('ScheduledPaymentInstallment', backref='scheduled_payment', lazy='dynamic')
    
    def __repr__(self):
        return f'<ScheduledPayment {self.id} - KSh {self.amount} {self.frequency}>'
    
    def calculate_next_payment_date(self):
        """Calculate the next payment date based on frequency"""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        if self.frequency == 'once':
            return None
        elif self.frequency == 'weekly':
            return self.next_payment_date + timedelta(weeks=1) if self.next_payment_date else self.start_date
        elif self.frequency == 'monthly':
            return self.next_payment_date + relativedelta(months=1) if self.next_payment_date else self.start_date
        return None


class ScheduledPaymentInstallment(db.Model):
    """Individual installments of scheduled payments"""
    __tablename__ = 'scheduled_payment_installments'
    
    id = db.Column(db.Integer, primary_key=True)
    scheduled_payment_id = db.Column(db.Integer, db.ForeignKey('scheduled_payments.id'), nullable=False)
    
    due_date = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0)
    
    payment_method = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(100), nullable=True)
    
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue, partial
    
    # Confirmation
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    confirmer = db.relationship('User', foreign_keys=[confirmed_by])
    
    def __repr__(self):
        return f'<Installment {self.id} - KSh {self.amount_due}>'


class FundTransfer(db.Model):
    """Fund transfers between chairs and finance"""
    __tablename__ = 'fund_transfers'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Transfer reference
    reference_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Amount being transferred
    amount = db.Column(db.Float, nullable=False)
    
    # Payment method (how the funds are transferred)
    payment_method = db.Column(db.String(50), default='cash')  # cash, mpesa_paybill, bank_transfer
    mpesa_reference = db.Column(db.String(100), nullable=True)  # M-Pesa transaction code if paid via paybill
    
    # Source (who is sending)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    from_role = db.Column(db.String(50), nullable=False)  # chair
    
    # Destination (who is receiving)
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_role = db.Column(db.String(50), nullable=False)  # finance
    
    # Transfer stage/flow
    # chair -> finance (direct)
    transfer_stage = db.Column(db.String(50), nullable=False)  # chair_to_finance
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    
    # Church hierarchy context
    local_church = db.Column(db.String(100), nullable=True)
    parish = db.Column(db.String(100), nullable=True)
    archdeaconry = db.Column(db.String(100), nullable=True)
    
    # Event context
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Description/notes
    description = db.Column(db.Text, nullable=True)
    
    # Supporting documents (receipts, etc.)
    attachments = db.Column(db.Text, default='[]')  # JSON array of file paths
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='sent_transfers')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='received_transfers')
    approvals = db.relationship('FundTransferApproval', backref='transfer', lazy='dynamic')
    
    def __repr__(self):
        return f'<FundTransfer {self.reference_number} - KSh {self.amount}>'
    
    @staticmethod
    def generate_reference():
        """Generate unique reference number"""
        import uuid
        year = datetime.utcnow().year
        unique_id = str(uuid.uuid4().hex)[:8].upper()
        return f"FT-{year}-{unique_id}"
    
    def get_attachments(self):
        """Parse attachments JSON"""
        try:
            return json.loads(self.attachments) if self.attachments else []
        except:
            return []
    
    def add_attachment(self, file_path):
        """Add an attachment"""
        attachments = self.get_attachments()
        attachments.append(file_path)
        self.attachments = json.dumps(attachments)
    
    def approve(self, user, notes=None):
        """Approve this transfer"""
        approval = FundTransferApproval(
            transfer_id=self.id,
            approved_by=user.id,
            action='approved',
            notes=notes
        )
        self.status = 'approved'
        self.approved_at = datetime.utcnow()
        db.session.add(self)
        db.session.add(approval)
        return approval
    
    def reject(self, user, reason):
        """Reject this transfer"""
        approval = FundTransferApproval(
            transfer_id=self.id,
            approved_by=user.id,
            action='rejected',
            notes=reason
        )
        self.status = 'rejected'
        db.session.add(self)
        db.session.add(approval)
        return approval
    
    def complete(self, user, notes=None):
        """Mark transfer as completed (funds received/confirmed)"""
        approval = FundTransferApproval(
            transfer_id=self.id,
            approved_by=user.id,
            action='completed',
            notes=notes
        )
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        db.session.add(self)
        db.session.add(approval)
        return approval


class FundTransferApproval(db.Model):
    """Approval history for fund transfers"""
    __tablename__ = 'fund_transfer_approvals'
    
    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey('fund_transfers.id'), nullable=False)
    
    # Who approved/rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Action taken
    action = db.Column(db.String(20), nullable=False)  # approved, rejected, completed
    
    # Notes/reason
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    approver = db.relationship('User', foreign_keys=[approved_by])
    
    def __repr__(self):
        return f'<FundTransferApproval {self.id} - {self.action}>'


class PaymentSummary(db.Model):
    """Summary of collections by chair for reporting"""
    __tablename__ = 'payment_summaries'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User who collected
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_role = db.Column(db.String(50), nullable=False)
    
    # Period
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    
    # Amounts
    total_delegate_payments = db.Column(db.Float, default=0)
    total_pledges_received = db.Column(db.Float, default=0)
    total_scheduled_payments = db.Column(db.Float, default=0)
    total_fundraising = db.Column(db.Float, default=0)
    
    grand_total = db.Column(db.Float, default=0)
    
    # Transfer status
    amount_transferred = db.Column(db.Float, default=0)
    amount_pending = db.Column(db.Float, default=0)
    
    # Church hierarchy
    local_church = db.Column(db.String(100), nullable=True)
    parish = db.Column(db.String(100), nullable=True)
    archdeaconry = db.Column(db.String(100), nullable=True)
    
    # Event context
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='payment_summaries')
    
    def __repr__(self):
        return f'<PaymentSummary {self.user_id} - KSh {self.grand_total}>'
    
    def calculate_totals(self):
        """Recalculate grand total"""
        self.grand_total = (
            self.total_delegate_payments +
            self.total_pledges_received +
            self.total_scheduled_payments +
            self.total_fundraising
        )
        self.amount_pending = self.grand_total - self.amount_transferred
