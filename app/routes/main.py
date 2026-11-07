from flask import Blueprint, render_template, redirect, url_for, send_from_directory, current_app, abort, flash, request
from flask_login import login_required, current_user
from app.models.delegate import Delegate
from app.models.payment import Payment
from app.models.user import User
from app import db
import os

main_bp = Blueprint('main', __name__)


@main_bp.route('/help')
@login_required
def help_page():
    """In-app help and tutorial page for chairs"""
    # Mark tutorial as seen when user visits the help page
    if not current_user.has_seen_tutorial:
        current_user.has_seen_tutorial = True
        db.session.commit()
    return render_template('help/index.html')


@main_bp.route('/help/chair-manual')
@login_required
def chair_manual():
    """Comprehensive training manual for Parish Chairs"""
    return render_template('help/chair_manual.html')


@main_bp.route('/tutorial/mark-seen', methods=['POST'])
@login_required
def mark_tutorial_seen():
    """Mark tutorial as seen for the current user"""
    current_user.has_seen_tutorial = True
    db.session.commit()
    flash('Welcome! You can access the tutorial anytime from the Help menu.', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(
            os.path.join(current_app.root_path, 'static', 'images'),
            'logo.png',
            mimetype='image/png'
        )
    except Exception:
        abort(404)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/app', methods=['GET', 'POST'])
@login_required
def app_home():
    """Masked URL endpoint - redirects to dashboard"""
    return redirect(url_for('main.dashboard'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    from app.models.event import Event
    
    # Get active event for countdown
    active_event = Event.query.filter_by(is_active=True).first()
    
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    
    # DYO (viewer) sees ALL delegates with detailed stats
    if current_user.role == 'viewer':
        delegates = Delegate.query.order_by(Delegate.registered_at.desc()).all()
        
        # Get all payments
        payments = Payment.query.filter_by(
            status='completed'
        ).order_by(Payment.created_at.desc()).limit(10).all()
        
        # Calculate overall stats
        total_delegates = len(delegates)
        paid_delegates = sum(1 for d in delegates if d.is_paid)
        unpaid_delegates = total_delegates - paid_delegates
        checked_in = sum(1 for d in delegates if d.checked_in)
        
        # Get total amount collected
        total_collected = Payment.get_total_collected()
        
        # Get stats by archdeaconry
        archdeaconry_stats = Delegate.get_stats_by_archdeaconry()
        
        # Get stats by parish
        parish_stats = Delegate.get_stats_by_parish()
        
        # Get gender stats
        gender_stats = Delegate.get_gender_stats()
        
        # Get category stats
        category_stats_raw = Delegate.get_category_stats()
        category_stats = [{'category': row.category or 'Delegate', 'count': row.count} for row in category_stats_raw]
        
        # Get age bracket stats
        age_bracket_stats_raw = Delegate.get_age_bracket_stats()
        age_bracket_labels = {
            '15_below': '15 and Below',
            '15_19': '15-19',
            '20_24': '20-24',
            '25_29': '25-29',
            '30_above': '30 and Above'
        }
        age_bracket_stats = [{'age_bracket': age_bracket_labels.get(row.age_bracket, row.age_bracket or 'Unknown'), 
                             'count': row.count} for row in age_bracket_stats_raw]
        
        # Get daily registration stats (last 30 days)
        daily_stats_raw = Delegate.get_daily_registration_stats(30)
        daily_stats = [{'date': str(row.date), 'count': row.count} for row in daily_stats_raw]
        
        # Total registered users (chairs)
        total_users = User.query.filter(User.role.in_(['chair', 'finance', 'registration_officer', 'data_clerk'])).count()
        
        return render_template('dashboard.html',
            delegates=delegates[:10],  # Show only last 10 in the list
            total_delegates=total_delegates,
            paid_delegates=paid_delegates,
            unpaid_delegates=unpaid_delegates,
            checked_in=checked_in,
            total_collected=total_collected,
            archdeaconry_stats=archdeaconry_stats,
            parish_stats=parish_stats,
            gender_stats=gender_stats,
            category_stats=category_stats,
            age_bracket_stats=age_bracket_stats,
            daily_stats=daily_stats,
            total_users=total_users,
            payments=payments,
            is_dyo=True,
            active_event=active_event
        )
    
    # Regular users see only their own delegates
    delegates = Delegate.query.filter_by(registered_by=current_user.id).order_by(Delegate.registered_at.desc()).all()
    
    # Get user's payments
    payments = Payment.query.filter_by(
        user_id=current_user.id
    ).order_by(Payment.created_at.desc()).limit(5).all()
    
    # Calculate stats
    total_delegates = len(delegates)
    paid_delegates = sum(1 for d in delegates if d.is_paid)
    # Truly unpaid = not paid AND not linked to any payment (including pending)
    truly_unpaid = sum(1 for d in delegates if not d.is_paid and d.payment_id is None)
    # Pending approval = not paid but has a payment_id (awaiting finance approval)
    pending_approval = sum(1 for d in delegates if not d.is_paid and d.payment_id is not None)
    unpaid_delegates = truly_unpaid  # Only show truly unpaid in the "Pay Now" notification
    
    return render_template('dashboard.html',
        delegates=delegates,
        total_delegates=total_delegates,
        paid_delegates=paid_delegates,
        unpaid_delegates=unpaid_delegates,
        pending_approval=pending_approval,
        payments=payments,
        is_dyo=False,
        active_event=active_event
    )
