from datetime import datetime
from app import db


class UserSession(db.Model):
    """Track active user sessions for session management"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    
    # Device/browser info
    device_info = db.Column(db.String(200), nullable=True)
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    
    # Location (approximate from IP)
    location = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_current = db.Column(db.Boolean, default=False)  # Mark current session
    
    # Relationship
    user = db.relationship('User', backref=db.backref('sessions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<UserSession {self.id} for user {self.user_id}>'
    
    @staticmethod
    def parse_user_agent(user_agent_string):
        """Parse user agent string to extract device info"""
        if not user_agent_string:
            return {
                'device': 'Unknown',
                'browser': 'Unknown',
                'os': 'Unknown'
            }
        
        ua = user_agent_string.lower()
        
        # Detect browser
        browser = 'Unknown'
        if 'edg/' in ua:
            browser = 'Edge'
        elif 'chrome' in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua:
            browser = 'Safari'
        elif 'opera' in ua or 'opr/' in ua:
            browser = 'Opera'
        
        # Detect OS
        os = 'Unknown'
        if 'windows' in ua:
            os = 'Windows'
        elif 'mac os' in ua or 'macintosh' in ua:
            os = 'macOS'
        elif 'linux' in ua:
            os = 'Linux'
        elif 'android' in ua:
            os = 'Android'
        elif 'iphone' in ua or 'ipad' in ua:
            os = 'iOS'
        
        # Detect device type
        device = 'Desktop'
        if 'mobile' in ua or 'android' in ua:
            device = 'Mobile'
        elif 'tablet' in ua or 'ipad' in ua:
            device = 'Tablet'
        
        return {
            'device': device,
            'browser': browser,
            'os': os
        }
    
    @classmethod
    def create_session(cls, user, session_token, ip_address=None, user_agent=None):
        """Create a new session record"""
        parsed = cls.parse_user_agent(user_agent)
        
        session_record = cls(
            user_id=user.id,
            session_token=session_token,
            device_info=parsed['device'],
            browser=parsed['browser'],
            os=parsed['os'],
            ip_address=ip_address,
            is_active=True,
            is_current=True
        )
        
        # Mark other sessions as not current
        cls.query.filter_by(user_id=user.id, is_current=True).update({'is_current': False})
        
        db.session.add(session_record)
        return session_record
    
    @classmethod
    def get_active_sessions(cls, user_id):
        """Get all active sessions for a user"""
        return cls.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(cls.last_activity.desc()).all()
    
    @classmethod
    def revoke_session(cls, session_id, user_id):
        """Revoke a specific session"""
        session_record = cls.query.filter_by(id=session_id, user_id=user_id).first()
        if session_record:
            session_record.is_active = False
            return True
        return False
    
    @classmethod
    def revoke_all_other_sessions(cls, user_id, current_token):
        """Revoke all sessions except the current one"""
        cls.query.filter(
            cls.user_id == user_id,
            cls.session_token != current_token,
            cls.is_active == True
        ).update({'is_active': False})
    
    @classmethod
    def update_activity(cls, session_token):
        """Update last activity timestamp"""
        session_record = cls.query.filter_by(session_token=session_token, is_active=True).first()
        if session_record:
            session_record.last_activity = datetime.utcnow()
    
    @classmethod
    def cleanup_old_sessions(cls, days=30):
        """Clean up sessions older than specified days"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        cls.query.filter(cls.last_activity < cutoff).delete()
