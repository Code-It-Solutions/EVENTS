from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.church_data import CHURCH_DATA, get_parishes

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/search')
@login_required
def global_search():
    """Global search API - searches delegates, users, payments, events"""
    from app.models.delegate import Delegate
    from app.models.user import User
    from app.models.payment import Payment
    from app.models.event import Event
    
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'results': []})
    
    results = []
    search_term = f'%{query}%'
    
    # Search Delegates
    delegates = Delegate.query.filter(
        (Delegate.full_name.ilike(search_term)) |
        (Delegate.phone.ilike(search_term)) |
        (Delegate.email.ilike(search_term)) |
        (Delegate.parish.ilike(search_term))
    ).limit(5).all()
    
    for d in delegates:
        results.append({
            'type': 'delegate',
            'icon': 'bi-person',
            'title': d.full_name,
            'subtitle': f'{d.parish} • {d.phone or "No phone"}',
            'url': f'/delegates/{d.id}',
            'badge': d.registration_status
        })
    
    # Search Users (admin only)
    if current_user.role in ['admin', 'super_admin']:
        users = User.query.filter(
            (User.name.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.phone.ilike(search_term))
        ).limit(5).all()
        
        for u in users:
            results.append({
                'type': 'user',
                'icon': 'bi-person-badge',
                'title': u.name,
                'subtitle': f'{u.role.title()} • {u.email}',
                'url': f'/admin/users/{u.id}',
                'badge': u.role
            })
    
    # Search Payments
    if current_user.role in ['admin', 'super_admin', 'finance', 'treasurer']:
        payments = Payment.query.filter(
            (Payment.transaction_code.ilike(search_term)) |
            (Payment.phone_number.ilike(search_term))
        ).limit(5).all()
        
        for p in payments:
            payer = p.delegate.full_name if p.delegate else (p.user.name if p.user else 'Unknown')
            results.append({
                'type': 'payment',
                'icon': 'bi-cash-coin',
                'title': f'KES {p.amount:,.0f} - {p.transaction_code or "No code"}',
                'subtitle': f'{payer} • {p.payment_date.strftime("%d %b %Y")}',
                'url': '/finance/',
                'badge': p.status
            })
    
    # Search Events
    events = Event.query.filter(
        (Event.name.ilike(search_term)) |
        (Event.venue.ilike(search_term))
    ).limit(3).all()
    
    for e in events:
        results.append({
            'type': 'event',
            'icon': 'bi-calendar-event',
            'title': e.name,
            'subtitle': f'{e.venue} • {e.start_date.strftime("%d %b %Y")}',
            'url': f'/events/{e.id}',
            'badge': 'Active' if e.is_active else 'Inactive'
        })
    
    return jsonify({'results': results, 'query': query})


@api_bp.route('/activity-feed')
@login_required
def activity_feed():
    """Get recent activity feed - registrations, payments, check-ins"""
    try:
        from app.models.delegate import Delegate
        from app.models.payment import Payment
        from app.models.user import User
        from datetime import datetime, timedelta
        
        activities = []
        
        # Get recent delegates (last 7 days)
        try:
            recent_delegates = Delegate.query.filter(
                Delegate.registered_at >= datetime.utcnow() - timedelta(days=7)
            ).order_by(Delegate.registered_at.desc()).limit(10).all()
            
            for d in recent_delegates:
                activities.append({
                    'type': 'registration',
                    'icon': 'bi-person-plus-fill',
                    'color': 'success',
                    'title': f'{d.name} registered',
                    'subtitle': f'{d.parish} • {d.archdeaconry}',
                    'time': d.registered_at.isoformat() if d.registered_at else '',
                    'time_ago': time_ago(d.registered_at) if d.registered_at else 'Unknown',
                    'url': f'/delegates/{d.id}'
                })
        except Exception as e:
            print(f"Activity feed - delegates error: {e}")
        
        # Get recent payments (last 7 days)
        if current_user.role in ['admin', 'super_admin', 'finance', 'treasurer']:
            try:
                recent_payments = Payment.query.filter(
                    Payment.payment_date >= datetime.utcnow() - timedelta(days=7),
                    Payment.status == 'completed'
                ).order_by(Payment.payment_date.desc()).limit(10).all()
                
                for p in recent_payments:
                    payer = p.delegate.full_name if p.delegate else (p.user.name if p.user else 'Unknown')
                    activities.append({
                        'type': 'payment',
                        'icon': 'bi-cash-coin',
                        'color': 'primary',
                        'title': f'KES {p.amount:,.0f} received',
                        'subtitle': f'From {payer} • {p.transaction_code or "Manual"}',
                        'time': p.payment_date.isoformat() if p.payment_date else '',
                        'time_ago': time_ago(p.payment_date) if p.payment_date else 'Unknown',
                        'url': '/finance/'
                    })
            except Exception as e:
                print(f"Activity feed - payments error: {e}")
        
        # Get recent check-ins (last 7 days)
        try:
            from app.models.operations import CheckInRecord
            recent_checkins = CheckInRecord.query.filter(
                CheckInRecord.checked_in_at >= datetime.utcnow() - timedelta(days=7)
            ).order_by(CheckInRecord.checked_in_at.desc()).limit(10).all()
            
            for c in recent_checkins:
                activities.append({
                    'type': 'checkin',
                    'icon': 'bi-check-circle-fill',
                    'color': 'info',
                    'title': f'{c.delegate.name if c.delegate else "Unknown"} checked in',
                    'subtitle': f'At {c.event.name if c.event else "Event"}',
                    'time': c.checked_in_at.isoformat() if c.checked_in_at else '',
                    'time_ago': time_ago(c.checked_in_at) if c.checked_in_at else 'Unknown',
                    'url': '/checkin/dashboard'
                })
        except Exception as e:
            print(f"Activity feed - checkins error: {e}")
        
        # Get recent user approvals (admin only)
        if current_user.role in ['admin', 'super_admin']:
            try:
                recent_users = User.query.filter(
                    User.created_at >= datetime.utcnow() - timedelta(days=7),
                    User.is_approved == True
                ).order_by(User.created_at.desc()).limit(5).all()
                
                for u in recent_users:
                    activities.append({
                        'type': 'user',
                        'icon': 'bi-person-check-fill',
                        'color': 'warning',
                        'title': f'{u.name} joined',
                        'subtitle': f'{u.role.title()} • {u.parish or "No parish"}',
                        'time': u.created_at.isoformat() if u.created_at else '',
                        'time_ago': time_ago(u.created_at) if u.created_at else 'Unknown',
                        'url': f'/admin/users/{u.id}'
                    })
            except Exception as e:
                print(f"Activity feed - users error: {e}")
        
        # Sort all activities by time (most recent first)
        activities.sort(key=lambda x: x['time'], reverse=True)
        
        return jsonify({
            'activities': activities[:20],  # Return top 20 activities
            'count': len(activities)
        })
    except Exception as e:
        print(f"Activity feed error: {e}")
        return jsonify({
            'activities': [],
            'count': 0,
            'error': str(e)
        })


def time_ago(dt):
    """Convert datetime to human-readable time ago string"""
    from datetime import datetime
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'Just now'
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f'{mins}m ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}h ago'
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f'{days}d ago'
    else:
        return dt.strftime('%d %b')


@api_bp.route('/parishes/<archdeaconry>')
def get_parishes_for_archdeaconry(archdeaconry):
    """API endpoint to get parishes for a specific archdeaconry"""
    if archdeaconry in CHURCH_DATA:
        parishes = sorted(CHURCH_DATA[archdeaconry])
        return jsonify({'parishes': parishes})
    return jsonify({'parishes': [], 'error': 'Archdeaconry not found'}), 404


@api_bp.route('/church-data')
def get_church_data():
    """API endpoint to get all church data"""
    return jsonify(CHURCH_DATA)


@api_bp.route('/notifications')
@login_required
def get_notifications():
    """Get notifications for current user"""
    try:
        from app.models.delegate import Delegate
        from app.models.payment import Payment
        from app.models.user import User
        from datetime import datetime, timedelta
        
        notifications = []
        
        # For admin/super_admin: pending user approvals
        if current_user.role in ['admin', 'super_admin']:
            try:
                pending_users = User.query.filter_by(is_approved=False).count()
                if pending_users > 0:
                    notifications.append({
                        'id': 'pending_users',
                        'type': 'warning',
                        'icon': 'bi-person-exclamation',
                        'title': f'{pending_users} User(s) Pending Approval',
                        'message': 'New registrations awaiting your review',
                        'url': '/admin/pending-approvals',
                        'time': 'Action needed'
                    })
            except:
                pass
        
        # For admin/finance: pending payment approvals
        if current_user.role in ['admin', 'super_admin', 'finance']:
            try:
                pending_payments = Payment.query.filter_by(status='pending').count()
                if pending_payments > 0:
                    notifications.append({
                        'id': 'pending_payments',
                        'type': 'info',
                        'icon': 'bi-cash-coin',
                        'title': f'{pending_payments} Payment(s) Pending',
                        'message': 'Payments awaiting verification',
                        'url': '/finance/',
                        'time': 'Action needed'
                    })
            except:
                pass
        
        # For all users: unpaid delegates reminder
        if current_user.role not in ['viewer']:
            try:
                if current_user.role in ['admin', 'super_admin']:
                    unpaid = Delegate.query.filter_by(is_paid=False).count()
                else:
                    unpaid = Delegate.query.filter_by(registered_by=current_user.id, is_paid=False).count()
                
                if unpaid > 0:
                    notifications.append({
                        'id': 'unpaid_delegates',
                        'type': 'warning',
                        'icon': 'bi-exclamation-triangle',
                        'title': f'{unpaid} Unpaid Delegate(s)',
                        'message': 'Complete payment to confirm registration',
                        'url': '/payments',
                        'time': 'Reminder'
                    })
            except:
                pass
        
        # Recent successful payments (last 24h) - for chair users
        if current_user.role not in ['admin', 'super_admin', 'finance', 'viewer']:
            try:
                recent_payments = Payment.query.filter(
                    Payment.user_id == current_user.id,
                    Payment.status == 'completed',
                    Payment.payment_date >= datetime.utcnow() - timedelta(hours=24)
                ).count()
                
                if recent_payments > 0:
                    notifications.append({
                        'id': 'recent_payments',
                        'type': 'success',
                        'icon': 'bi-check-circle',
                        'title': f'{recent_payments} Payment(s) Approved',
                        'message': 'Your recent payments have been confirmed',
                        'url': '/payments/history',
                        'time': 'Last 24h'
                    })
            except:
                pass
        
        # Admin: recent registrations
        if current_user.role in ['admin', 'super_admin', 'viewer']:
            try:
                today_registrations = Delegate.query.filter(
                    Delegate.registered_at >= datetime.utcnow() - timedelta(hours=24)
                ).count()
                
                if today_registrations > 0:
                    notifications.append({
                        'id': 'today_registrations',
                        'type': 'success',
                        'icon': 'bi-person-plus',
                        'title': f'{today_registrations} New Registration(s)',
                        'message': 'Delegates registered in the last 24 hours',
                        'url': '/delegates',
                        'time': 'Last 24h'
                    })
            except:
                pass
        
        return jsonify({
            'notifications': notifications,
            'unread_count': len([n for n in notifications if n['type'] in ['warning', 'info']])
        })
    except Exception as e:
        return jsonify({
            'notifications': [],
            'unread_count': 0
        })


@api_bp.route('/check-duplicate')
@login_required
def check_duplicate():
    """Check for potential duplicate delegates by name or phone"""
    from app.models.delegate import Delegate
    from difflib import SequenceMatcher
    
    name = request.args.get('name', '').strip()
    phone = request.args.get('phone', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)  # Exclude when editing
    
    duplicates = []
    
    # Check phone number (exact match)
    if phone and len(phone) >= 9:
        # Normalize phone number
        normalized_phone = phone.replace(' ', '').replace('-', '')
        if normalized_phone.startswith('0'):
            normalized_phone = '254' + normalized_phone[1:]
        elif normalized_phone.startswith('+'):
            normalized_phone = normalized_phone[1:]
        
        phone_matches = Delegate.query.filter(
            Delegate.phone_number.ilike(f'%{normalized_phone[-9:]}%')
        ).all()
        
        for d in phone_matches:
            if exclude_id and d.id == exclude_id:
                continue
            duplicates.append({
                'id': d.id,
                'name': d.full_name,
                'phone': d.phone_number,
                'parish': d.parish,
                'match_type': 'phone',
                'confidence': 100
            })
    
    # Check name similarity (fuzzy match)
    if name and len(name) >= 3:
        # Get all delegates for comparison
        all_delegates = Delegate.query.all()
        name_lower = name.lower()
        
        for d in all_delegates:
            if exclude_id and d.id == exclude_id:
                continue
            
            # Skip if already matched by phone
            if any(dup['id'] == d.id for dup in duplicates):
                continue
            
            delegate_name = (d.full_name or '').lower()
            
            # Calculate similarity ratio
            ratio = SequenceMatcher(None, name_lower, delegate_name).ratio()
            
            if ratio >= 0.8:  # 80% similarity threshold
                duplicates.append({
                    'id': d.id,
                    'name': d.full_name,
                    'phone': d.phone_number,
                    'parish': d.parish,
                    'match_type': 'name',
                    'confidence': int(ratio * 100)
                })
    
    # Sort by confidence
    duplicates.sort(key=lambda x: x['confidence'], reverse=True)
    
    return jsonify({
        'duplicates': duplicates[:5],  # Return top 5 matches
        'has_duplicates': len(duplicates) > 0
    })
