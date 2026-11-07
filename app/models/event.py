from datetime import datetime
from app import db
import json


class Event(db.Model):
    """Events table - supports multiple events"""
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)  # URL-friendly identifier
    description = db.Column(db.Text, nullable=True)
    
    # Event dates
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    registration_deadline = db.Column(db.DateTime, nullable=True)
    
    # Venue
    venue = db.Column(db.String(200), nullable=True)
    venue_address = db.Column(db.Text, nullable=True)
    
    # Branding
    logo_url = db.Column(db.String(500), nullable=True)
    primary_color = db.Column(db.String(7), default='#4e73df')  # Hex color
    secondary_color = db.Column(db.String(7), default='#858796')
    
    # Capacity
    max_delegates = db.Column(db.Integer, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    
    # Custom fields (JSON)
    custom_fields = db.Column(db.Text, default='[]')  # JSON array of field definitions
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    pricing_tiers = db.relationship('PricingTier', backref='event', lazy='dynamic', cascade='all, delete-orphan')
    delegates = db.relationship('Delegate', backref='event', lazy='dynamic')
    
    def __repr__(self):
        return f'<Event {self.name}>'
    
    def get_custom_fields(self):
        """Parse custom fields JSON"""
        try:
            return json.loads(self.custom_fields) if self.custom_fields else []
        except:
            return []
    
    def set_custom_fields(self, fields):
        """Set custom fields as JSON"""
        self.custom_fields = json.dumps(fields)
    
    def get_current_price(self):
        """Get the current applicable pricing tier"""
        now = datetime.utcnow()
        tier = PricingTier.query.filter(
            PricingTier.event_id == self.id,
            PricingTier.is_active == True,
            db.or_(PricingTier.valid_from == None, PricingTier.valid_from <= now),
            db.or_(PricingTier.valid_until == None, PricingTier.valid_until >= now)
        ).order_by(PricingTier.price.asc()).first()
        return tier
    
    def get_delegate_count(self):
        """Get current delegate count"""
        return self.delegates.count()
    
    def get_paid_delegate_count(self):
        """Get paid delegate count"""
        return self.delegates.filter_by(is_paid=True).count()
    
    def get_checked_in_count(self):
        """Get checked-in delegate count"""
        return self.delegates.filter_by(checked_in=True).count()
    
    def is_registration_open(self):
        """Check if registration is still open"""
        if not self.is_active or not self.is_published:
            return False
        if self.registration_deadline and datetime.utcnow() > self.registration_deadline:
            return False
        if self.max_delegates and self.get_delegate_count() >= self.max_delegates:
            return False
        return True
    
    def get_days_count(self):
        """Get number of days for this event"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 1
    
    @staticmethod
    def get_active_events():
        """Get all active events"""
        return Event.query.filter_by(is_active=True).order_by(Event.start_date.desc()).all()


class PricingTier(db.Model):
    """Pricing tiers for events - Early bird, Regular, VIP, etc."""
    __tablename__ = 'pricing_tiers'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    
    name = db.Column(db.String(50), nullable=False)  # Early Bird, Regular, VIP
    description = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Float, nullable=False)
    
    # Category restrictions (JSON array of allowed categories)
    allowed_categories = db.Column(db.Text, default='[]')
    
    # Time-based validity
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    
    # Capacity limits
    max_tickets = db.Column(db.Integer, nullable=True)
    tickets_sold = db.Column(db.Integer, default=0)
    
    # Group discounts
    group_min_size = db.Column(db.Integer, nullable=True)  # Min delegates for group discount
    group_discount_percent = db.Column(db.Float, nullable=True)  # e.g., 10 for 10% off
    
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<PricingTier {self.name} - KSh {self.price}>'
    
    def get_allowed_categories(self):
        """Parse allowed categories JSON"""
        try:
            return json.loads(self.allowed_categories) if self.allowed_categories else []
        except:
            return []
    
    def set_allowed_categories(self, categories):
        """Set allowed categories as JSON"""
        self.allowed_categories = json.dumps(categories)
    
    def is_available(self):
        """Check if this tier is currently available"""
        if not self.is_active:
            return False
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_tickets and self.tickets_sold >= self.max_tickets:
            return False
        return True
    
    def calculate_price(self, delegate_count=1):
        """Calculate price with group discount if applicable"""
        base_total = self.price * delegate_count
        if self.group_min_size and delegate_count >= self.group_min_size and self.group_discount_percent:
            discount = base_total * (self.group_discount_percent / 100)
            return base_total - discount
        return base_total
