"""
Pending Delegate Model for self-registration workflow
Delegates can register themselves via a public link, pending chairperson approval
"""
from datetime import datetime
import secrets
from app import db


class PendingDelegate(db.Model):
    """Pending delegates awaiting chairperson approval"""
    __tablename__ = 'pending_delegates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Unique registration token for tracking
    registration_token = db.Column(db.String(64), unique=True, nullable=False)
    
    # Delegate information (same as Delegate model)
    name = db.Column(db.String(100), nullable=False)
    local_church = db.Column(db.String(100), nullable=False)
    parish = db.Column(db.String(100), nullable=False)
    archdeaconry = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15), nullable=True)
    id_number = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)  # For notifications
    gender = db.Column(db.String(10), nullable=False)
    age_bracket = db.Column(db.String(20), nullable=True)  # Age bracket
    category = db.Column(db.String(20), default='delegate')
    
    # Event (optional - for multi-event support)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    # Status tracking
    status = db.Column(db.String(20), nullable=False, default='pending')
    # Status: pending, approved, rejected, expired
    
    # Timestamps
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    
    # Reviewer info (chairperson who approved/rejected)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewer_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    # Created delegate ID (after approval)
    delegate_id = db.Column(db.Integer, db.ForeignKey('delegates.id'), nullable=True)
    
    # Relationships
    reviewer = db.relationship('User', backref='reviewed_pending_delegates')
    delegate = db.relationship('Delegate', backref='pending_registration')
    event = db.relationship('Event', backref='pending_delegates')
    
    def __repr__(self):
        return f'<PendingDelegate {self.name} - {self.status}>'
    
    @staticmethod
    def generate_token():
        """Generate a unique registration token"""
        return secrets.token_urlsafe(32)
    
    def to_dict(self):
        return {
            'id': self.id,
            'registration_token': self.registration_token,
            'name': self.name,
            'local_church': self.local_church,
            'parish': self.parish,
            'archdeaconry': self.archdeaconry,
            'phone_number': self.phone_number,
            'id_number': self.id_number,
            'email': self.email,
            'gender': self.gender,
            'age_bracket': self.age_bracket,
            'category': self.category,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.name if self.reviewer else None,
            'reviewer_notes': self.reviewer_notes,
            'rejection_reason': self.rejection_reason
        }
    
    @staticmethod
    def get_pending_count_for_church(local_church=None, parish=None, archdeaconry=None):
        """Get count of pending registrations for a specific church/parish/archdeaconry"""
        query = PendingDelegate.query.filter_by(status='pending')
        
        if local_church:
            query = query.filter_by(local_church=local_church)
        if parish:
            query = query.filter_by(parish=parish)
        if archdeaconry:
            query = query.filter_by(archdeaconry=archdeaconry)
        
        return query.count()
    
    @staticmethod
    def get_pending_for_user(user):
        """
        Get pending registrations that a user can approve.
        - Admins see all pending registrations
        - Chairs see registrations from their local church, parish, or archdeaconry
        """
        from sqlalchemy import func
        
        query = PendingDelegate.query.filter_by(status='pending')
        
        if user.role in ['admin', 'super_admin']:
            # Admins see all pending registrations
            return query.order_by(PendingDelegate.submitted_at.desc()).all()
        
        elif user.role == 'chair':
            # Chairs see registrations matching their location hierarchy
            # Priority: local_church > parish > archdeaconry
            if user.local_church:
                # Case-insensitive match on local church
                results = query.filter(
                    func.lower(PendingDelegate.local_church) == func.lower(user.local_church)
                ).order_by(PendingDelegate.submitted_at.desc()).all()
                if results:
                    return results
            
            if user.parish:
                # Fall back to parish if no local church match
                results = query.filter(
                    func.lower(PendingDelegate.parish) == func.lower(user.parish)
                ).order_by(PendingDelegate.submitted_at.desc()).all()
                if results:
                    return results
            
            if user.archdeaconry:
                # Fall back to archdeaconry if no parish match
                results = query.filter(
                    func.lower(PendingDelegate.archdeaconry) == func.lower(user.archdeaconry)
                ).order_by(PendingDelegate.submitted_at.desc()).all()
                if results:
                    return results
            
            # If chair has no location set, show all (they need to set their profile)
            if not user.local_church and not user.parish and not user.archdeaconry:
                return query.order_by(PendingDelegate.submitted_at.desc()).all()
        
        return []
