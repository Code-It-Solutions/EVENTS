from datetime import datetime
import uuid
import io
import base64

# Optional qrcode import - may not be available on all platforms
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

from app import db


class Delegate(db.Model):
    """Delegates table - people being registered for the event"""
    __tablename__ = 'delegates'
    
    # Categories exempt from registration fees
    FEE_EXEMPT_CATEGORIES = ['nav', 'arise_band']
    
    # Categories with reduced fees (500 KSh instead of 1000 KSh)
    REDUCED_FEE_CATEGORIES = ['counsellor', 'intercessor']
    
    # Age bracket choices
    AGE_BRACKETS = [
        ('15_below', '15 and Below'),
        ('15_19', '15-19'),
        ('20_24', '20-24'),
        ('25_29', '25-29'),
        ('30_above', '30 and Above')
    ]
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    delegate_number = db.Column(db.Integer, nullable=True)  # Auto-assigned sequential number
    name = db.Column(db.String(100), nullable=False)
    local_church = db.Column(db.String(100), nullable=False)
    parish = db.Column(db.String(100), nullable=False)
    archdeaconry = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15), nullable=True)
    id_number = db.Column(db.String(20), nullable=True)  # National ID for duplicate detection
    gender = db.Column(db.String(10), nullable=False)  # male, female
    age_bracket = db.Column(db.String(20), nullable=True)  # Age bracket: 15_below, 15_19, 20_24, 25_29, 30_above
    category = db.Column(db.String(20), default='delegate')  # delegate, leader, speaker, vip
    
    # Multi-event support
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    pricing_tier_id = db.Column(db.Integer, db.ForeignKey('pricing_tiers.id'), nullable=True)
    
    # Custom field values (JSON)
    custom_field_values = db.Column(db.Text, default='{}')
    
    # Registration details
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Payment status
    is_paid = db.Column(db.Boolean, default=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=True)
    amount_paid = db.Column(db.Float, default=0)
    payment_confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    payment_confirmed_at = db.Column(db.DateTime, nullable=True)
    
    # Check-in tracking
    checked_in = db.Column(db.Boolean, default=False)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    pricing_tier = db.relationship('PricingTier', backref='delegates')
    check_in_records = db.relationship('CheckInRecord', backref='delegate', lazy='dynamic')
    payment_reminders = db.relationship('PaymentReminder', backref='delegate', lazy='dynamic')
    
    def __repr__(self):
        return f'<Delegate {self.name}>'
    
    def is_fee_exempt(self):
        """Check if this delegate is exempt from registration fees"""
        return self.category in self.FEE_EXEMPT_CATEGORIES
    
    def is_reduced_fee(self):
        """Check if this delegate has reduced registration fee"""
        return self.category in self.REDUCED_FEE_CATEGORIES
    
    def get_registration_fee(self):
        """Get the registration fee for this delegate based on category"""
        if self.is_fee_exempt():
            return 0
        
        # Check if delegate has reduced fee (counsellors, intercessors)
        from flask import current_app
        if self.is_reduced_fee():
            return current_app.config.get('REDUCED_FEE', 500)
        
        # Check if delegate has a pricing tier
        if self.pricing_tier:
            return self.pricing_tier.price
        
        # Fall back to default fee from config
        return current_app.config.get('DELEGATE_FEE', 1000)
    
    def get_custom_field_values(self):
        """Parse custom field values JSON"""
        import json
        try:
            return json.loads(self.custom_field_values) if self.custom_field_values else {}
        except:
            return {}
    
    def set_custom_field_values(self, values):
        """Set custom field values as JSON"""
        import json
        self.custom_field_values = json.dumps(values)
    
    @staticmethod
    def generate_ticket_number(event=None, max_retries=10):
        """
        Generate a unique ticket number like KAYO-2025-XXXX.
        Uses the highest existing number + 1 to avoid duplicates.
        Includes retry logic for race conditions.
        """
        import random
        year = datetime.utcnow().year
        prefix = event.slug.upper() if event and event.slug else 'KAYO'
        
        for attempt in range(max_retries):
            # Find the highest ticket number for this prefix and year
            pattern = f"{prefix}-{year}-%"
            
            # Query to find the max number
            existing = Delegate.query.filter(
                Delegate.ticket_number.like(pattern)
            ).order_by(Delegate.ticket_number.desc()).first()
            
            if existing and existing.ticket_number:
                try:
                    # Extract the number part (last segment after the last dash)
                    last_num = int(existing.ticket_number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            # Add a small random offset on retries to avoid collisions
            if attempt > 0:
                next_num += random.randint(1, 10)
            
            ticket_number = f"{prefix}-{year}-{next_num:04d}"
            
            # Verify it doesn't already exist
            if not Delegate.query.filter_by(ticket_number=ticket_number).first():
                return ticket_number
        
        # Fallback: use timestamp-based unique number
        import time
        unique_suffix = int(time.time() * 1000) % 100000
        return f"{prefix}-{year}-{unique_suffix:05d}"
    
    @staticmethod
    def get_next_delegate_number(event_id=None):
        """Get next sequential delegate number - guaranteed unique"""
        # Find the max delegate number for this event
        max_num = db.session.query(db.func.max(Delegate.delegate_number)).filter(
            Delegate.event_id == event_id if event_id else True
        ).scalar()
        return (max_num or 0) + 1
    
    def generate_qr_code(self):
        """Generate QR code for this delegate"""
        if not HAS_QRCODE:
            # Return a placeholder if qrcode module not available
            return None
        
        qr_data = f"KAYO|{self.ticket_number}|{self.name}|{self.phone_number or 'N/A'}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for embedding in HTML
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode()
    
    @staticmethod
    def check_duplicate(phone_number=None, id_number=None, exclude_id=None, event_id=None):
        """Check for duplicate registrations"""
        duplicates = []
        
        if phone_number:
            query = Delegate.query.filter(Delegate.phone_number == phone_number)
            if exclude_id:
                query = query.filter(Delegate.id != exclude_id)
            if query.first():
                duplicates.append(f"Phone number {phone_number} already registered")
        
        if id_number:
            query = Delegate.query.filter(Delegate.id_number == id_number)
            if exclude_id:
                query = query.filter(Delegate.id != exclude_id)
            if query.first():
                duplicates.append(f"ID number {id_number} already registered")
        
        return duplicates
    
    @staticmethod
    def get_stats_by_archdeaconry():
        """Get delegate counts grouped by archdeaconry"""
        return db.session.query(
            Delegate.archdeaconry,
            db.func.count(Delegate.id).label('total'),
            db.func.sum(db.case((Delegate.is_paid == True, 1), else_=0)).label('paid'),
            db.func.sum(db.case((Delegate.is_paid == False, 1), else_=0)).label('unpaid')
        ).group_by(Delegate.archdeaconry).all()
    
    @staticmethod
    def get_stats_by_parish():
        """Get delegate counts grouped by parish"""
        return db.session.query(
            Delegate.parish,
            Delegate.archdeaconry,
            db.func.count(Delegate.id).label('total'),
            db.func.sum(db.case((Delegate.is_paid == True, 1), else_=0)).label('paid'),
            db.func.sum(db.case((Delegate.is_paid == False, 1), else_=0)).label('unpaid')
        ).group_by(Delegate.parish, Delegate.archdeaconry).all()
    
    @staticmethod
    def get_gender_stats():
        """Get delegate counts by gender"""
        return db.session.query(
            Delegate.gender,
            db.func.count(Delegate.id).label('count')
        ).group_by(Delegate.gender).all()
    
    @staticmethod
    def get_daily_registration_stats(days=30):
        """Get registration counts for the last N days"""
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=days)
        return db.session.query(
            db.func.date(Delegate.registered_at).label('date'),
            db.func.count(Delegate.id).label('count')
        ).filter(Delegate.registered_at >= start_date)\
         .group_by(db.func.date(Delegate.registered_at))\
         .order_by(db.func.date(Delegate.registered_at)).all()
    
    @staticmethod
    def get_category_stats():
        """Get delegate counts by category"""
        return db.session.query(
            Delegate.category,
            db.func.count(Delegate.id).label('count')
        ).group_by(Delegate.category).all()
    
    @staticmethod
    def get_age_bracket_stats():
        """Get delegate counts by age bracket"""
        return db.session.query(
            Delegate.age_bracket,
            db.func.count(Delegate.id).label('count')
        ).group_by(Delegate.age_bracket).all()
    
    def get_age_bracket_display(self):
        """Get human-readable age bracket name"""
        bracket_map = dict(self.AGE_BRACKETS)
        return bracket_map.get(self.age_bracket, self.age_bracket or 'Not specified')
    
    @staticmethod
    def search(query):
        """Smart search across multiple fields"""
        search_term = f"%{query}%"
        return Delegate.query.filter(
            db.or_(
                Delegate.name.ilike(search_term),
                Delegate.phone_number.ilike(search_term),
                Delegate.id_number.ilike(search_term),
                Delegate.ticket_number.ilike(search_term),
                Delegate.local_church.ilike(search_term),
                Delegate.parish.ilike(search_term),
                Delegate.archdeaconry.ilike(search_term)
            )
        ).all()
