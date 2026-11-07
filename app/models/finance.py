"""
Financial Management Models
Professional double-entry bookkeeping system for KAYO
"""
from datetime import datetime
from app import db


class AccountCategory(db.Model):
    """Chart of Accounts Categories"""
    __tablename__ = 'account_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)  # e.g., 1000, 2000, 3000
    type = db.Column(db.String(50), nullable=False)  # asset, liability, equity, income, expense
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    accounts = db.relationship('Account', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<AccountCategory {self.code} - {self.name}>'


class Account(db.Model):
    """Chart of Accounts - Individual accounts"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)  # e.g., 1001, 1002
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('account_categories.id'), nullable=True)
    account_type = db.Column(db.String(50), nullable=False)  # asset, liability, equity, income, expense
    normal_balance = db.Column(db.String(10), nullable=False)  # debit or credit
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # System accounts can't be deleted
    opening_balance = db.Column(db.Float, default=0.0)
    current_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    journal_lines = db.relationship('JournalLine', backref='account', lazy='dynamic')
    
    def __repr__(self):
        return f'<Account {self.code} - {self.name}>'
    
    def get_balance(self, as_of_date=None):
        """Calculate account balance as of a specific date"""
        query = JournalLine.query.filter_by(account_id=self.id)
        if as_of_date:
            query = query.join(JournalEntry).filter(JournalEntry.date <= as_of_date)
        
        total_debit = sum(line.debit or 0 for line in query.filter(JournalEntry.status == 'posted').all())
        total_credit = sum(line.credit or 0 for line in query.filter(JournalEntry.status == 'posted').all())
        
        if self.normal_balance == 'debit':
            return self.opening_balance + total_debit - total_credit
        else:
            return self.opening_balance + total_credit - total_debit
    
    def update_balance(self):
        """Recalculate and update current balance"""
        self.current_balance = self.get_balance()
        return self.current_balance


class JournalEntry(db.Model):
    """Journal Entries - Main transaction records"""
    __tablename__ = 'journal_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=False)
    reference = db.Column(db.String(100))  # External reference (voucher, receipt, etc.)
    entry_type = db.Column(db.String(50), default='general')  # general, adjusting, closing, reversing
    status = db.Column(db.String(20), default='draft')  # draft, posted, voided
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_at = db.Column(db.DateTime)
    voided_at = db.Column(db.DateTime)
    voided_reason = db.Column(db.Text)
    
    # Optional links
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'))
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'))
    
    # Relationships
    lines = db.relationship('JournalLine', backref='entry', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_entries')
    poster = db.relationship('User', foreign_keys=[posted_by], backref='posted_entries')
    
    def __repr__(self):
        return f'<JournalEntry {self.entry_number}>'
    
    @staticmethod
    def generate_entry_number():
        """Generate unique entry number"""
        today = datetime.utcnow()
        prefix = f"JE-{today.strftime('%Y%m')}"
        last_entry = JournalEntry.query.filter(
            JournalEntry.entry_number.like(f'{prefix}%')
        ).order_by(JournalEntry.id.desc()).first()
        
        if last_entry:
            last_num = int(last_entry.entry_number.split('-')[-1])
            return f"{prefix}-{str(last_num + 1).zfill(4)}"
        return f"{prefix}-0001"
    
    def is_balanced(self):
        """Check if debits equal credits"""
        total_debit = sum(line.debit or 0 for line in self.lines)
        total_credit = sum(line.credit or 0 for line in self.lines)
        return abs(total_debit - total_credit) < 0.01
    
    def get_total_debit(self):
        return sum(line.debit or 0 for line in self.lines)
    
    def get_total_credit(self):
        return sum(line.credit or 0 for line in self.lines)
    
    def post(self, user_id):
        """Post the journal entry"""
        if not self.is_balanced():
            raise ValueError("Journal entry is not balanced")
        
        self.status = 'posted'
        self.posted_by = user_id
        self.posted_at = datetime.utcnow()
        
        # Update account balances
        for line in self.lines:
            line.account.update_balance()
    
    def void(self, user_id, reason):
        """Void the journal entry"""
        self.status = 'voided'
        self.voided_at = datetime.utcnow()
        self.voided_reason = reason
        
        # Update account balances
        for line in self.lines:
            line.account.update_balance()


class JournalLine(db.Model):
    """Journal Entry Lines - Individual debit/credit entries"""
    __tablename__ = 'journal_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    description = db.Column(db.String(255))
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f'<JournalLine {self.account.code if self.account else "?"}: Dr {self.debit} Cr {self.credit}>'


class Voucher(db.Model):
    """Financial Vouchers - Payment and Receipt vouchers"""
    __tablename__ = 'vouchers'
    
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True, nullable=False)
    voucher_type = db.Column(db.String(20), nullable=False)  # payment, receipt, journal
    date = db.Column(db.Date, nullable=False)
    
    # Party details
    payee_name = db.Column(db.String(200))  # Who receives/pays
    payee_type = db.Column(db.String(50))  # delegate, vendor, staff, other
    
    # Amount details
    amount = db.Column(db.Float, nullable=False)
    amount_in_words = db.Column(db.String(255))
    
    # Payment method
    payment_method = db.Column(db.String(50))  # cash, mpesa, bank_transfer, cheque
    reference_number = db.Column(db.String(100))  # Cheque no, M-Pesa code, etc.
    bank_name = db.Column(db.String(100))
    
    # Purpose
    narration = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))  # registration, transport, accommodation, supplies, etc.
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, pending_approval, approved, paid, cancelled
    
    # Approval workflow
    prepared_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # Notes
    notes = db.Column(db.Text)
    
    # Link to journal entry
    journal_entries = db.relationship('JournalEntry', backref='voucher', lazy='dynamic')
    
    # Relationships for users
    preparer = db.relationship('User', foreign_keys=[prepared_by], backref='prepared_vouchers')
    checker = db.relationship('User', foreign_keys=[checked_by], backref='checked_vouchers')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_vouchers')
    
    # Line items
    items = db.relationship('VoucherItem', backref='voucher', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Voucher {self.voucher_number}>'
    
    @staticmethod
    def generate_voucher_number(voucher_type):
        """Generate unique voucher number"""
        today = datetime.utcnow()
        prefix_map = {
            'payment': 'PV',
            'receipt': 'RV',
            'journal': 'JV'
        }
        prefix = prefix_map.get(voucher_type, 'V')
        full_prefix = f"{prefix}-{today.strftime('%Y%m')}"
        
        last_voucher = Voucher.query.filter(
            Voucher.voucher_number.like(f'{full_prefix}%')
        ).order_by(Voucher.id.desc()).first()
        
        if last_voucher:
            last_num = int(last_voucher.voucher_number.split('-')[-1])
            return f"{full_prefix}-{str(last_num + 1).zfill(4)}"
        return f"{full_prefix}-0001"


class VoucherItem(db.Model):
    """Voucher Line Items - Individual items in a voucher"""
    __tablename__ = 'voucher_items'
    
    id = db.Column(db.Integer, primary_key=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey('vouchers.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Float, default=1)
    unit_price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))  # Expense/Income account
    
    account = db.relationship('Account')


class FinancialPeriod(db.Model):
    """Financial Periods for reporting"""
    __tablename__ = 'financial_periods'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "KAYO 2024", "Q1 2024"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_closed = db.Column(db.Boolean, default=False)
    closed_at = db.Column(db.DateTime)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BudgetLine(db.Model):
    """Budget Lines for expense tracking"""
    __tablename__ = 'budget_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('financial_periods.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    budgeted_amount = db.Column(db.Float, nullable=False, default=0)
    actual_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    period = db.relationship('FinancialPeriod', backref='budget_lines')
    account = db.relationship('Account', backref='budget_lines')
    
    @property
    def variance(self):
        return self.budgeted_amount - self.actual_amount
    
    @property
    def variance_percentage(self):
        if self.budgeted_amount == 0:
            return 0
        return (self.variance / self.budgeted_amount) * 100
