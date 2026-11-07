from datetime import datetime
from app import db


class PermissionRequest(db.Model):
    """Permission requests for users to add delegates"""
    __tablename__ = 'permission_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Request details
    permission_type = db.Column(db.String(50), nullable=False, default='delegate_registration')
    # Types: delegate_registration, bulk_upload, payment_confirmation
    
    reason = db.Column(db.Text, nullable=True)  # User's reason for requesting
    scope = db.Column(db.String(50), nullable=True)  # parish, archdeaconry, all
    scope_value = db.Column(db.String(100), nullable=True)  # Specific parish/archdeaconry name
    
    # Status tracking
    status = db.Column(db.String(20), nullable=False, default='pending')
    # Status: pending, approved, rejected, expired
    
    # Timestamps
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # For temporary permissions
    
    # Reviewer info
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewer_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    requester = db.relationship('User', foreign_keys=[user_id], backref='permission_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f'<PermissionRequest {self.id} - {self.requester.name if self.requester else "Unknown"} - {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.requester.name if self.requester else None,
            'user_email': self.requester.email if self.requester else None,
            'user_phone': self.requester.phone if self.requester else None,
            'user_parish': self.requester.parish if self.requester else None,
            'user_archdeaconry': self.requester.archdeaconry if self.requester else None,
            'user_role': self.requester.role if self.requester else None,
            'permission_type': self.permission_type,
            'reason': self.reason,
            'scope': self.scope,
            'scope_value': self.scope_value,
            'status': self.status,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.name if self.reviewer else None,
            'reviewer_notes': self.reviewer_notes
        }
    
    @staticmethod
    def get_pending_count():
        """Get count of pending requests"""
        return PermissionRequest.query.filter_by(status='pending').count()
    
    @staticmethod
    def has_pending_request(user_id, permission_type='delegate_registration'):
        """Check if user already has a pending request"""
        return PermissionRequest.query.filter_by(
            user_id=user_id,
            permission_type=permission_type,
            status='pending'
        ).first() is not None
    
    @staticmethod
    def get_approved_permission(user_id, permission_type='delegate_registration'):
        """Get user's approved permission if exists and not expired"""
        request = PermissionRequest.query.filter_by(
            user_id=user_id,
            permission_type=permission_type,
            status='approved'
        ).first()
        
        if request:
            # Check if expired
            if request.expires_at and request.expires_at < datetime.utcnow():
                request.status = 'expired'
                db.session.commit()
                return None
        
        return request
