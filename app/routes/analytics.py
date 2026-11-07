from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from app.utils.analytics import Analytics

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function


@analytics_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Main analytics dashboard"""
    try:
        event_id = request.args.get('event_id', type=int) or (
            current_user.current_event_id if current_user.current_event_id else None
        )
        
        # Get all analytics data with error handling
        try:
            forecast = Analytics.get_revenue_forecast(event_id, days_ahead=30)
        except Exception as e:
            print(f"Analytics forecast error: {e}")
            forecast = {'error': str(e)}
        
        try:
            regions = Analytics.get_regional_performance(event_id)
        except Exception as e:
            print(f"Analytics regions error: {e}")
            regions = []
        
        try:
            demographics = Analytics.get_demographic_insights(event_id)
        except Exception as e:
            print(f"Analytics demographics error: {e}")
            demographics = {}
        
        try:
            payment_behavior = Analytics.get_payment_behavior(event_id)
        except Exception as e:
            print(f"Analytics payment_behavior error: {e}")
            payment_behavior = {}
        
        try:
            registration_trend = Analytics.get_registration_trend(event_id, days=30)
        except Exception as e:
            print(f"Analytics registration_trend error: {e}")
            registration_trend = []
        
        return render_template('analytics/dashboard.html',
            forecast=forecast,
            regions=regions,
            demographics=demographics,
            payment_behavior=payment_behavior,
            registration_trend=registration_trend,
            event_id=event_id
        )
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))


@analytics_bp.route('/api/forecast')
@login_required
@admin_required
def api_forecast():
    """API endpoint for revenue forecast"""
    event_id = request.args.get('event_id', type=int)
    days = request.args.get('days', 30, type=int)
    
    forecast = Analytics.get_revenue_forecast(event_id, days)
    return jsonify(forecast)


@analytics_bp.route('/api/regions')
@login_required
@admin_required
def api_regions():
    """API endpoint for regional performance"""
    event_id = request.args.get('event_id', type=int)
    regions = Analytics.get_regional_performance(event_id)
    return jsonify(regions)


@analytics_bp.route('/api/demographics')
@login_required
@admin_required
def api_demographics():
    """API endpoint for demographic insights"""
    event_id = request.args.get('event_id', type=int)
    demographics = Analytics.get_demographic_insights(event_id)
    return jsonify(demographics)


@analytics_bp.route('/api/payment-behavior')
@login_required
@admin_required
def api_payment_behavior():
    """API endpoint for payment behavior analytics"""
    event_id = request.args.get('event_id', type=int)
    days = request.args.get('days', 30, type=int)
    
    behavior = Analytics.get_payment_behavior(event_id, days)
    return jsonify(behavior)


@analytics_bp.route('/api/registration-trend')
@login_required
@admin_required
def api_registration_trend():
    """API endpoint for registration trend"""
    event_id = request.args.get('event_id', type=int)
    days = request.args.get('days', 30, type=int)
    
    trend = Analytics.get_registration_trend(event_id, days)
    return jsonify(trend)
