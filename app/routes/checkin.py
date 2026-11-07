from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
from app import db
from app.models.delegate import Delegate
from app.models.event import Event
from app.models.operations import CheckInRecord

checkin_bp = Blueprint('checkin', __name__, url_prefix='/checkin')


def staff_required(f):
    """Decorator to require staff or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== QR SCANNER ====================

@checkin_bp.route('/scanner')
@login_required
def qr_scanner():
    """Web-based QR code scanner"""
    events = Event.query.filter_by(is_active=True).all()
    
    # Get sessions for today (can be configured per event)
    sessions = [
        {'id': 'morning', 'name': 'Morning Session', 'time': '8:00 AM - 12:00 PM'},
        {'id': 'afternoon', 'name': 'Afternoon Session', 'time': '2:00 PM - 5:00 PM'},
        {'id': 'evening', 'name': 'Evening Session', 'time': '6:00 PM - 9:00 PM'},
        {'id': 'workshop_a', 'name': 'Workshop A', 'time': 'As scheduled'},
        {'id': 'workshop_b', 'name': 'Workshop B', 'time': 'As scheduled'},
        {'id': 'plenary', 'name': 'Plenary Session', 'time': 'As scheduled'},
    ]
    
    return render_template('checkin/scanner.html', events=events, sessions=sessions)


@checkin_bp.route('/api/scan', methods=['POST'])
@login_required
def process_scan():
    """Process QR code scan and check in delegate"""
    data = request.get_json()
    
    qr_data = data.get('qr_data', '').strip()
    event_id = data.get('event_id')
    session_name = data.get('session_name')
    
    if not qr_data:
        return jsonify({'success': False, 'error': 'No QR data provided'})
    
    # Parse QR data - could be ticket number, delegate number, pipe-separated format, or full URL
    delegate = None
    search_value = qr_data
    
    # Handle pipe-separated format: KAYO|ticket_number|name|phone
    if '|' in qr_data:
        parts = qr_data.split('|')
        if len(parts) >= 2:
            search_value = parts[1]  # ticket_number is second part
    
    # Handle DELEGATE-ID format (fallback from badges when no ticket number)
    if search_value.startswith('DELEGATE-'):
        try:
            delegate_id = int(search_value.replace('DELEGATE-', ''))
            delegate = Delegate.query.get(delegate_id)
        except ValueError:
            pass
    
    # Try different formats if not found yet
    if not delegate:
        if search_value.startswith('KAYO-') or '-' in search_value:
            # Ticket number format (e.g., KAYO-2025-0001 or EVENT-2025-0001)
            delegate = Delegate.query.filter_by(ticket_number=search_value).first()
        elif search_value.isdigit():
            # Delegate ID or delegate number
            delegate = Delegate.query.filter_by(id=int(search_value)).first()
            if not delegate:
                delegate = Delegate.query.filter_by(delegate_number=search_value).first()
        elif '/delegates/' in search_value:
            # URL format - extract ID
            try:
                delegate_id = int(search_value.split('/delegates/')[-1].split('/')[0])
                delegate = Delegate.query.get(delegate_id)
            except:
                pass
        else:
            # Try as ticket number or delegate number
            delegate = Delegate.query.filter_by(ticket_number=search_value).first()
            if not delegate:
                delegate = Delegate.query.filter_by(delegate_number=search_value).first()
    
    if not delegate:
        return jsonify({
            'success': False, 
            'error': f'Delegate not found for QR: {qr_data[:50]}',
            'qr_data': qr_data[:50]
        })
    
    # Determine event
    if not event_id:
        # Use delegate's event or first active event
        event_id = delegate.event_id or Event.query.filter_by(is_active=True).first()
        if hasattr(event_id, 'id'):
            event_id = event_id.id
    
    if not event_id:
        return jsonify({'success': False, 'error': 'No active event found'})
    
    # Check if already checked in today for this session
    today = datetime.utcnow().date()
    existing_query = CheckInRecord.query.filter_by(
        delegate_id=delegate.id,
        event_id=event_id,
        check_in_date=today
    )
    
    if session_name:
        existing_query = existing_query.filter_by(session_name=session_name)
    
    existing = existing_query.first()
    
    if existing:
        return jsonify({
            'success': False,
            'error': 'Already checked in',
            'delegate': {
                'id': delegate.id,
                'name': delegate.name,
                'ticket_number': delegate.ticket_number,
                'category': delegate.delegate_category,
                'checked_in_at': existing.check_in_time.strftime('%I:%M %p')
            },
            'already_checked_in': True
        })
    
    # Create check-in record
    check_in = CheckInRecord(
        delegate_id=delegate.id,
        event_id=event_id,
        check_in_date=today,
        check_in_time=datetime.utcnow(),
        checked_in_by=current_user.id,
        session_name=session_name,
        check_in_method='qr_scan'
    )
    db.session.add(check_in)
    
    # Update delegate's checked_in status
    delegate.checked_in = True
    delegate.check_in_time = datetime.utcnow()
    
    db.session.commit()
    
    # Get event name
    event = Event.query.get(event_id)
    
    return jsonify({
        'success': True,
        'message': 'Check-in successful!',
        'delegate': {
            'id': delegate.id,
            'name': delegate.name,
            'ticket_number': delegate.ticket_number,
            'category': delegate.delegate_category,
            'parish': delegate.parish,
            'archdeaconry': delegate.archdeaconry,
            'payment_status': delegate.payment_status,
            'photo_url': delegate.photo_url
        },
        'check_in': {
            'time': check_in.check_in_time.strftime('%I:%M %p'),
            'session': session_name,
            'event': event.name if event else 'Unknown Event'
        }
    })


@checkin_bp.route('/api/manual', methods=['POST'])
@login_required
def manual_checkin():
    """Manual check-in by searching delegate"""
    data = request.get_json()
    
    delegate_id = data.get('delegate_id')
    event_id = data.get('event_id')
    session_name = data.get('session_name')
    
    if not delegate_id:
        return jsonify({'success': False, 'error': 'Delegate ID required'})
    
    delegate = Delegate.query.get(delegate_id)
    if not delegate:
        return jsonify({'success': False, 'error': 'Delegate not found'})
    
    # Reuse scan logic
    request_data = {
        'qr_data': str(delegate_id),
        'event_id': event_id,
        'session_name': session_name
    }
    
    # Process as scan
    return process_scan_internal(delegate, event_id, session_name)


def process_scan_internal(delegate, event_id, session_name):
    """Internal function to process check-in"""
    if not event_id:
        event_id = delegate.event_id or Event.query.filter_by(is_active=True).first()
        if hasattr(event_id, 'id'):
            event_id = event_id.id
    
    if not event_id:
        return jsonify({'success': False, 'error': 'No active event found'})
    
    today = datetime.utcnow().date()
    existing_query = CheckInRecord.query.filter_by(
        delegate_id=delegate.id,
        event_id=event_id,
        check_in_date=today
    )
    
    if session_name:
        existing_query = existing_query.filter_by(session_name=session_name)
    
    existing = existing_query.first()
    
    if existing:
        return jsonify({
            'success': False,
            'error': 'Already checked in',
            'delegate': {
                'id': delegate.id,
                'name': delegate.name,
                'ticket_number': delegate.ticket_number,
                'category': delegate.delegate_category,
                'checked_in_at': existing.check_in_time.strftime('%I:%M %p')
            },
            'already_checked_in': True
        })
    
    check_in = CheckInRecord(
        delegate_id=delegate.id,
        event_id=event_id,
        check_in_date=today,
        check_in_time=datetime.utcnow(),
        checked_in_by=current_user.id,
        session_name=session_name,
        check_in_method='manual'
    )
    db.session.add(check_in)
    
    delegate.checked_in = True
    delegate.check_in_time = datetime.utcnow()
    
    db.session.commit()
    
    event = Event.query.get(event_id)
    
    return jsonify({
        'success': True,
        'message': 'Check-in successful!',
        'delegate': {
            'id': delegate.id,
            'name': delegate.name,
            'ticket_number': delegate.ticket_number,
            'category': delegate.delegate_category,
            'parish': delegate.parish,
            'archdeaconry': delegate.archdeaconry,
            'payment_status': delegate.payment_status
        },
        'check_in': {
            'time': check_in.check_in_time.strftime('%I:%M %p'),
            'session': session_name,
            'event': event.name if event else 'Unknown Event'
        }
    })


# ==================== CHECK-IN DASHBOARD ====================

@checkin_bp.route('/dashboard')
@login_required
def dashboard():
    """Check-in dashboard showing arrivals and attendance"""
    event_id = request.args.get('event_id', type=int)
    selected_date = request.args.get('date')
    session_filter = request.args.get('session')
    
    # Get active events
    events = Event.query.filter_by(is_active=True).all()
    
    # Default to first active event
    if not event_id and events:
        event_id = events[0].id
    
    # Parse date or default to today
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    # Get check-in records for the day
    query = CheckInRecord.query.filter_by(check_in_date=filter_date)
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    if session_filter:
        query = query.filter_by(session_name=session_filter)
    
    check_ins = query.order_by(CheckInRecord.check_in_time.desc()).all()
    
    # Get delegate details for each check-in
    arrivals = []
    for ci in check_ins:
        delegate = Delegate.query.get(ci.delegate_id)
        if delegate:
            arrivals.append({
                'id': ci.id,
                'delegate_id': delegate.id,
                'name': delegate.name,
                'ticket_number': delegate.ticket_number,
                'category': delegate.delegate_category,
                'parish': delegate.parish,
                'archdeaconry': delegate.archdeaconry,
                'payment_status': delegate.payment_status,
                'arrival_time': ci.check_in_time,
                'session': ci.session_name,
                'method': ci.check_in_method
            })
    
    # Calculate stats
    total_registered = Delegate.query.count()
    if event_id:
        total_registered = Delegate.query.filter_by(event_id=event_id).count()
    
    total_arrived = len(arrivals)
    unique_delegates = len(set(a['delegate_id'] for a in arrivals))
    
    # Session breakdown
    session_counts = {}
    for ci in check_ins:
        session = ci.session_name or 'General'
        session_counts[session] = session_counts.get(session, 0) + 1
    
    # Hourly breakdown for chart
    hourly_counts = {}
    for ci in check_ins:
        hour = ci.check_in_time.strftime('%I %p')
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    # Category breakdown
    category_counts = {}
    for a in arrivals:
        cat = a['category'] or 'Unknown'
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Get sessions for filter
    sessions = db.session.query(CheckInRecord.session_name).filter(
        CheckInRecord.session_name.isnot(None)
    ).distinct().all()
    sessions = [s[0] for s in sessions if s[0]]
    
    return render_template('checkin/dashboard.html',
        events=events,
        selected_event_id=event_id,
        selected_date=filter_date,
        selected_session=session_filter,
        arrivals=arrivals,
        total_registered=total_registered,
        total_arrived=total_arrived,
        unique_delegates=unique_delegates,
        session_counts=session_counts,
        hourly_counts=hourly_counts,
        category_counts=category_counts,
        sessions=sessions
    )


@checkin_bp.route('/api/live-arrivals')
@login_required
def live_arrivals():
    """API for live arrival updates"""
    event_id = request.args.get('event_id', type=int)
    since = request.args.get('since')  # Timestamp
    
    today = date.today()
    query = CheckInRecord.query.filter_by(check_in_date=today)
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    if since:
        try:
            since_time = datetime.fromisoformat(since)
            query = query.filter(CheckInRecord.check_in_time > since_time)
        except:
            pass
    
    check_ins = query.order_by(CheckInRecord.check_in_time.desc()).limit(50).all()
    
    arrivals = []
    for ci in check_ins:
        delegate = Delegate.query.get(ci.delegate_id)
        if delegate:
            arrivals.append({
                'id': ci.id,
                'delegate_id': delegate.id,
                'name': delegate.name,
                'ticket_number': delegate.ticket_number,
                'category': delegate.delegate_category,
                'parish': delegate.parish,
                'payment_status': delegate.payment_status,
                'arrival_time': ci.check_in_time.isoformat(),
                'arrival_time_formatted': ci.check_in_time.strftime('%I:%M %p'),
                'session': ci.session_name,
                'method': ci.check_in_method
            })
    
    # Stats
    total_today = CheckInRecord.query.filter_by(check_in_date=today).count()
    
    return jsonify({
        'arrivals': arrivals,
        'total_today': total_today,
        'timestamp': datetime.utcnow().isoformat()
    })


@checkin_bp.route('/api/search-delegate')
@login_required
def search_delegate():
    """Search for delegate by name, phone, or ticket"""
    q = request.args.get('q', '').strip()
    
    if len(q) < 2:
        return jsonify({'results': []})
    
    delegates = Delegate.query.filter(
        db.or_(
            Delegate.name.ilike(f'%{q}%'),
            Delegate.phone_number.ilike(f'%{q}%'),
            Delegate.ticket_number.ilike(f'%{q}%'),
            Delegate.delegate_number.ilike(f'%{q}%')
        )
    ).limit(10).all()
    
    results = []
    for d in delegates:
        # Check if already checked in today
        today_checkin = CheckInRecord.query.filter_by(
            delegate_id=d.id,
            check_in_date=date.today()
        ).first()
        
        results.append({
            'id': d.id,
            'name': d.name,
            'ticket_number': d.ticket_number,
            'category': d.delegate_category,
            'parish': d.parish,
            'payment_status': d.payment_status,
            'checked_in_today': today_checkin is not None,
            'check_in_time': today_checkin.check_in_time.strftime('%I:%M %p') if today_checkin else None
        })
    
    return jsonify({'results': results})


@checkin_bp.route('/api/undo/<int:checkin_id>', methods=['POST'])
@login_required
def undo_checkin(checkin_id):
    """Undo a check-in (admin only)"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Admin access required'})
    
    checkin = CheckInRecord.query.get(checkin_id)
    if not checkin:
        return jsonify({'success': False, 'error': 'Check-in record not found'})
    
    delegate = Delegate.query.get(checkin.delegate_id)
    
    db.session.delete(checkin)
    
    # Check if delegate has any other check-ins today
    other_checkins = CheckInRecord.query.filter_by(
        delegate_id=checkin.delegate_id,
        check_in_date=date.today()
    ).first()
    
    if not other_checkins and delegate:
        delegate.checked_in = False
        delegate.check_in_time = None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Check-in undone successfully'
    })


# ==================== SESSION ATTENDANCE ====================

@checkin_bp.route('/sessions')
@login_required
def session_attendance():
    """View attendance by session"""
    event_id = request.args.get('event_id', type=int)
    selected_date = request.args.get('date')
    
    events = Event.query.filter_by(is_active=True).all()
    
    if not event_id and events:
        event_id = events[0].id
    
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    # Get all sessions for the day
    sessions_query = db.session.query(
        CheckInRecord.session_name,
        db.func.count(CheckInRecord.id).label('count'),
        db.func.min(CheckInRecord.check_in_time).label('first_arrival'),
        db.func.max(CheckInRecord.check_in_time).label('last_arrival')
    ).filter_by(check_in_date=filter_date)
    
    if event_id:
        sessions_query = sessions_query.filter_by(event_id=event_id)
    
    sessions_data = sessions_query.group_by(CheckInRecord.session_name).all()
    
    sessions = []
    for session_name, count, first, last in sessions_data:
        sessions.append({
            'name': session_name or 'General Check-in',
            'count': count,
            'first_arrival': first.strftime('%I:%M %p') if first else 'N/A',
            'last_arrival': last.strftime('%I:%M %p') if last else 'N/A'
        })
    
    # Get total registered delegates for the event
    total_registered = Delegate.query.filter_by(event_id=event_id).count() if event_id else Delegate.query.count()
    
    return render_template('checkin/sessions.html',
        events=events,
        selected_event_id=event_id,
        selected_date=filter_date,
        sessions=sessions,
        total_registered=total_registered
    )
