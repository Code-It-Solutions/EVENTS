from datetime import datetime, timedelta
import secrets
import random
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask import session
from app import db, login_manager


class User(UserMixin, db.Model):
    """Users table for Chairs, Finance, and Admins"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=True)
    role = db.Column(db.String(20), nullable=False, default='chair')  # Legacy role field
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)  # New RBAC
    password_hash = db.Column(db.String(256), nullable=True)  # Nullable for OAuth users
    local_church = db.Column(db.String(100), nullable=True)
    parish = db.Column(db.String(100), nullable=True)
    archdeaconry = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Admin approval fields
    is_approved = db.Column(db.Boolean, default=False)  # Requires admin approval
    approval_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    
    # Session management - for single session restriction
    session_token = db.Column(db.String(64), nullable=True)
    
    # OTP fields for login verification
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Google OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_picture = db.Column(db.String(500), nullable=True)
    oauth_provider = db.Column(db.String(20), nullable=True)  # 'google', 'local', etc.
    
    # Multi-event support
    current_event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Tutorial tracking
    has_seen_tutorial = db.Column(db.Boolean, default=False)
    
    # Relationships
    delegates = db.relationship('Delegate', backref='registered_by_user', lazy='dynamic',
                               foreign_keys='Delegate.registered_by')
    payments = db.relationship('Payment', backref='user', lazy='dynamic',
                              foreign_keys='Payment.user_id')
    assigned_role = db.relationship('Role', backref='users', foreign_keys=[role_id])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False  # OAuth users without password
        return check_password_hash(self.password_hash, password)
    
    def generate_session_token(self):
        """Generate a new session token for single-session enforcement"""
        self.session_token = secrets.token_hex(32)
        return self.session_token
    
    def verify_session_token(self, token):
        """Verify if the provided session token matches"""
        return self.session_token == token
    
    def generate_otp(self):
        """Generate a 6-digit OTP for email verification"""
        self.otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        return self.otp_code
    
    def verify_otp(self, otp):
        """Verify if the provided OTP is valid and not expired"""
        if not self.otp_code or not self.otp_expires_at:
            return False
        if datetime.utcnow() > self.otp_expires_at:
            return False
        return self.otp_code == otp
    
    def clear_otp(self):
        """Clear OTP after successful verification"""
        self.otp_code = None
        self.otp_expires_at = None
    
    @classmethod
    def get_parish_chair(cls, parish):
        """Get the approved chair for a parish, if any"""
        return cls.query.filter_by(
            parish=parish,
            role='chair',
            is_approved=True,
            is_active=True
        ).first()
    
    @classmethod
    def parish_has_chair(cls, parish):
        """Check if a parish already has an approved chair"""
        return cls.get_parish_chair(parish) is not None
    
    @classmethod
    def get_pending_registrations(cls):
        """Get all pending registration requests"""
        return cls.query.filter_by(
            approval_status='pending',
            role='chair'
        ).order_by(cls.created_at.desc()).all()
    
    def is_admin(self):
        return self.role == 'admin' or self.role == 'super_admin'
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def has_permission(self, permission):
        """Check if user has a specific permission via RBAC"""
        # Super admins have all permissions
        if self.role == 'super_admin' or self.role == 'admin':
            return True
        # Check role-based permissions
        if self.assigned_role:
            return self.assigned_role.has_permission(permission)
        return False
    
    def get_current_event(self):
        """Get user's current active event"""
        from app.models.event import Event
        if self.current_event_id:
            return Event.query.get(self.current_event_id)
        # Return first active event if none selected
        return Event.query.filter_by(is_active=True).first()
    
    def get_unpaid_delegates_count(self):
        """Get count of delegates not yet paid for"""
        from app.models.delegate import Delegate
        return Delegate.query.filter_by(
            registered_by=self.id,
            is_paid=False
        ).count()
    
    def get_total_amount_due(self):
        """Calculate total amount due for unpaid delegates"""
        from flask import current_app
        return self.get_unpaid_delegates_count() * current_app.config['DELEGATE_FEE']
    
    def log_activity(self, action, resource_type, resource_id=None, description=None, 
                    old_values=None, new_values=None):
        """Log user activity"""
        from flask import request
        from app.models.audit import AuditLog
        return AuditLog.log(
            user=self,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            event_id=self.current_event_id
        )
    
    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(id):
    user = User.query.get(int(id))
    if user:
        # Verify session token for single-session enforcement
        stored_token = session.get('session_token')
        if stored_token and user.session_token:
            if stored_token != user.session_token:
                # Session was invalidated (user logged in elsewhere)
                return None
    return user
