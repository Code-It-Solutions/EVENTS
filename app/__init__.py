from flask import Flask, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config

# Optional Flask-Mail import
try:
    from flask_mail import Mail
    HAS_MAIL = True
except ImportError:
    HAS_MAIL = False
    Mail = None

# Optional CORS import for mobile API
try:
    from flask_cors import CORS
    HAS_CORS = True
except ImportError:
    HAS_CORS = False

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
csrf = CSRFProtect()
mail = Mail() if HAS_MAIL else None


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    if HAS_MAIL and mail:
        mail.init_app(app)
    
    # Enable CORS for mobile API endpoints
    if HAS_CORS:
        CORS(app, resources={r"/api/v1/*": {"origins": "*"}})

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.delegates import delegates_bp
    from app.routes.payments import payments_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.events import events_bp
    from app.routes.settings import settings_bp
    from app.routes.analytics import analytics_bp
    from app.routes.communications import communications_bp
    from app.routes.badges import badges_bp
    from app.routes.checkin import checkin_bp
    from app.routes.mobile_api import mobile_api_bp
    from app.routes.fund_management import bp as fund_management_bp
    from app.routes.public import public_bp
    from app.routes.finance import finance_bp
    from app.routes.budget import budget_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(delegates_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(communications_bp)
    app.register_blueprint(badges_bp)
    app.register_blueprint(checkin_bp)
    app.register_blueprint(mobile_api_bp)
    app.register_blueprint(fund_management_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(budget_bp)
    
    # Exempt API blueprints from CSRF (they use JWT authentication instead)
    csrf.exempt(api_bp)
    csrf.exempt(mobile_api_bp)
    
    # Import all models to ensure they are registered with SQLAlchemy
    from app.models import user, delegate, event, payment, audit, permission_request, fund_management, operations
    
    # Custom Jinja filter for heatmap colors
    def get_heatmap_color(intensity):
        """Generate heatmap color based on intensity (0-1)"""
        colors = ['#f0f9e8', '#bae4bc', '#7bccc4', '#43a2ca', '#0868ac']
        if intensity <= 0:
            return colors[0]
        elif intensity < 0.25:
            return colors[1]
        elif intensity < 0.5:
            return colors[2]
        elif intensity < 0.75:
            return colors[3]
        else:
            return colors[4]
    
    app.jinja_env.globals['get_heatmap_color'] = get_heatmap_color
    
    # Make csrf_token() available in all templates
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    
    # Inject pending registration count for admin navigation
    @app.context_processor
    def inject_pending_count():
        if current_user.is_authenticated and current_user.is_admin():
            from app.models.user import User
            pending_count = User.query.filter_by(approval_status='pending', role='chair').count()
            return dict(pending_registration_count=pending_count)
        return dict(pending_registration_count=0)
    
    # Custom unauthorized handler for session invalidation
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import redirect, url_for, request
        # Check if this was a session invalidation (logged in elsewhere)
        if session.get('session_token') and not current_user.is_authenticated:
            session.clear()
            flash('You have been logged out because your account was accessed from another device.', 'warning')
        else:
            flash('Please log in to access this page.', 'info')
        return redirect(url_for('auth.login', next=request.url))

    return app
