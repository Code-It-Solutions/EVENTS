from datetime import datetime
from app import db


class Payment(db.Model):
    """Payments table - M-Pesa transactions"""
    __tablename__ = 'payments'
    
    # Finance approval status choices
    FINANCE_STATUS_PENDING = 'pending_approval'
    FINANCE_STATUS_APPROVED = 'approved'
    FINANCE_STATUS_REJECTED = 'rejected'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(50), default='M-Pesa Paybill')
    
    # M-Pesa specific fields
    transaction_id = db.Column(db.String(50), unique=True, nullable=True)
    mpesa_receipt_number = db.Column(db.String(50), nullable=True)
    checkout_request_id = db.Column(db.String(100), nullable=True)
    merchant_request_id = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(15), nullable=True)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    result_code = db.Column(db.String(10), nullable=True)
    result_desc = db.Column(db.String(200), nullable=True)
    
    # Finance approval workflow
    finance_status = db.Column(db.String(30), default='pending_approval')  # pending_approval, approved, rejected
    confirmed_by_chair_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    confirmed_by_chair_at = db.Column(db.DateTime, nullable=True)
    approved_by_finance_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_by_finance_at = db.Column(db.DateTime, nullable=True)
    finance_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Number of delegates this payment covers
    delegates_count = db.Column(db.Integer, nullable=False, default=0)
    
    # Relationships
    delegates = db.relationship('Delegate', backref='payment', lazy='dynamic')
    confirmed_by_chair = db.relationship('User', foreign_keys=[confirmed_by_chair_id], backref='chair_confirmed_payments')
    approved_by_finance = db.relationship('User', foreign_keys=[approved_by_finance_id], backref='finance_approved_payments')
    
    def __repr__(self):
        return f'<Payment {self.id} - KSh {self.amount}>'
    
    def is_pending_finance_approval(self):
        """Check if payment is waiting for finance approval"""
        return self.finance_status == self.FINANCE_STATUS_PENDING
    
    def is_finance_approved(self):
        """Check if payment has been approved by finance"""
        return self.finance_status == self.FINANCE_STATUS_APPROVED
    
    def approve_by_finance(self, finance_user_id, notes=None):
        """Approve payment by finance - this completes the payment"""
        self.finance_status = self.FINANCE_STATUS_APPROVED
        self.approved_by_finance_id = finance_user_id
        self.approved_by_finance_at = datetime.utcnow()
        self.finance_notes = notes
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
    
    def reject_by_finance(self, finance_user_id, reason):
        """Reject payment by finance"""
        self.finance_status = self.FINANCE_STATUS_REJECTED
        self.approved_by_finance_id = finance_user_id
        self.approved_by_finance_at = datetime.utcnow()
        self.rejection_reason = reason
        self.status = 'failed'
    
    def mark_completed(self, mpesa_receipt, transaction_id=None):
        """Mark payment as completed and update related delegates"""
        self.status = 'completed'
        self.mpesa_receipt_number = mpesa_receipt
        self.transaction_id = transaction_id or mpesa_receipt
        self.completed_at = datetime.utcnow()
        
        # Mark all linked delegates as paid
        for delegate in self.delegates:
            delegate.is_paid = True
    
    def mark_failed(self, result_code, result_desc):
        """Mark payment as failed"""
        self.status = 'failed'
        self.result_code = result_code
        self.result_desc = result_desc
    
    @staticmethod
    def get_total_collected():
        """Get total amount collected (only finance-approved payments)"""
        result = db.session.query(
            db.func.sum(Payment.amount)
        ).filter(
            Payment.status == 'completed',
            Payment.finance_status == Payment.FINANCE_STATUS_APPROVED
        ).scalar()
        return result or 0
    
    @staticmethod
    def get_pending_approval_total():
        """Get total amount pending finance approval"""
        result = db.session.query(
            db.func.sum(Payment.amount)
        ).filter(
            Payment.finance_status == Payment.FINANCE_STATUS_PENDING
        ).scalar()
        return result or 0
    
    @staticmethod
    def get_payment_stats():
        """Get payment statistics"""
        return db.session.query(
            Payment.status,
            db.func.count(Payment.id).label('count'),
            db.func.sum(Payment.amount).label('total')
        ).group_by(Payment.status).all()
