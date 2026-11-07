from datetime import datetime
from app import db
import json


class AuditLog(db.Model):
    """Audit logs for tracking all system activities"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Who performed the action
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_email = db.Column(db.String(120), nullable=True)  # Store email for reference
    
    # What action was performed
    action = db.Column(db.String(50), nullable=False)  # login, logout, create, update, delete, payment, check_in
    resource_type = db.Column(db.String(50), nullable=False)  # user, delegate, payment, event
    resource_id = db.Column(db.Integer, nullable=True)
    
    # Details
    description = db.Column(db.Text, nullable=True)
    old_values = db.Column(db.Text, nullable=True)  # JSON of previous values
    new_values = db.Column(db.Text, nullable=True)  # JSON of new values
    
    # Context
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Event context (for multi-event support)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    
    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_email}>'
    
    def get_old_values(self):
        """Parse old values JSON"""
        try:
            return json.loads(self.old_values) if self.old_values else {}
        except:
            return {}
    
    def get_new_values(self):
        """Parse new values JSON"""
        try:
            return json.loads(self.new_values) if self.new_values else {}
        except:
            return {}
    
    @staticmethod
    def log(user, action, resource_type, resource_id=None, description=None, 
            old_values=None, new_values=None, ip_address=None, user_agent=None, event_id=None):
        """Create an audit log entry"""
        log = AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else 'system',
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            ip_address=ip_address,
            user_agent=user_agent,
            event_id=event_id
        )
        db.session.add(log)
        return log
    
    @staticmethod
    def get_recent(limit=50, action=None, resource_type=None, user_id=None):
        """Get recent audit logs with optional filters"""
        query = AuditLog.query
        if action:
            query = query.filter_by(action=action)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_user_activity(user_id, days=30):
        """Get a user's activity for the last N days"""
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=days)
        return AuditLog.query.filter(
            AuditLog.user_id == user_id,
            AuditLog.created_at >= start_date
        ).order_by(AuditLog.created_at.desc()).all()


class Role(db.Model):
    """Roles for role-based access control"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    
    # Permissions (stored as JSON)
    permissions = db.Column(db.Text, default='[]')
    
    # System role (cannot be deleted)
    is_system = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    def get_permissions(self):
        """Parse permissions JSON"""
        try:
            return json.loads(self.permissions) if self.permissions else []
        except:
            return []
    
    def set_permissions(self, perms):
        """Set permissions as JSON"""
        self.permissions = json.dumps(perms)
    
    def has_permission(self, permission):
        """Check if role has a specific permission"""
        perms = self.get_permissions()
        # Check for wildcard permission
        if '*' in perms:
            return True
        return permission in perms
    
    @staticmethod
    def create_default_roles():
        """Create default system roles"""
        roles = [
            {
                'name': 'super_admin',
                'description': 'Full system access',
                'permissions': ['*'],
                'is_system': True
            },
            {
                'name': 'admin',
                'description': 'Event administration',
                'permissions': [
                    'delegates.view', 'delegates.create', 'delegates.edit', 'delegates.delete',
                    'payments.view', 'payments.process',
                    'reports.view', 'reports.export',
                    'check_in.manage',
                    'events.view'
                ],
                'is_system': True
            },
            {
                'name': 'finance',
                'description': 'Financial operations',
                'permissions': [
                    'delegates.view',
                    'payments.view', 'payments.process', 'payments.refund',
                    'reports.view', 'reports.export',
                    'reconciliation.manage'
                ],
                'is_system': True
            },
            {
                'name': 'registration_officer',
                'description': 'Delegate registration',
                'permissions': [
                    'delegates.view', 'delegates.create', 'delegates.edit',
                    'payments.view', 'payments.process',
                    'check_in.manage'
                ],
                'is_system': True
            },
            {
                'name': 'data_clerk',
                'description': 'Data entry only',
                'permissions': [
                    'delegates.view', 'delegates.create',
                    'check_in.view'
                ],
                'is_system': True
            },
            {
                'name': 'viewer',
                'description': 'Read-only access',
                'permissions': [
                    'delegates.view',
                    'payments.view',
                    'reports.view'
                ],
                'is_system': True
            },
            {
                'name': 'chair',
                'description': 'Church Chair - can register delegates from their church',
                'permissions': [
                    'delegates.view', 'delegates.create', 'delegates.edit',
                    'payments.view', 'payments.process',
                    'check_in.view'
                ],
                'is_system': True
            }
        ]
        
        for role_data in roles:
            existing = Role.query.filter_by(name=role_data['name']).first()
            if not existing:
                role = Role(
                    name=role_data['name'],
                    description=role_data['description'],
                    is_system=role_data['is_system']
                )
                role.set_permissions(role_data['permissions'])
                db.session.add(role)
        
        db.session.commit()


# Available permissions
PERMISSIONS = {
    'delegates.view': 'View delegates',
    'delegates.create': 'Create delegates',
    'delegates.edit': 'Edit delegates',
    'delegates.delete': 'Delete delegates',
    'delegates.export': 'Export delegate data',
    'payments.view': 'View payments',
    'payments.process': 'Process payments',
    'payments.refund': 'Process refunds',
    'reports.view': 'View reports',
    'reports.export': 'Export reports',
    'check_in.view': 'View check-in status',
    'check_in.manage': 'Manage check-ins',
    'events.view': 'View events',
    'events.create': 'Create events',
    'events.edit': 'Edit events',
    'events.delete': 'Delete events',
    'users.view': 'View users',
    'users.create': 'Create users',
    'users.edit': 'Edit users',
    'users.delete': 'Delete users',
    'audit.view': 'View audit logs',
    'settings.manage': 'Manage system settings',
    'reconciliation.manage': 'Manage payment reconciliation'
}
