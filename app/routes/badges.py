from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from functools import wraps
from io import BytesIO
import zipfile
from app import db
from app.models.delegate import Delegate
from app.models.event import Event

# Optional badge designer import
try:
    from app.utils.badges import BadgeDesigner
    HAS_BADGE_DESIGNER = True
except ImportError:
    HAS_BADGE_DESIGNER = False
    BadgeDesigner = None

badges_bp = Blueprint('badges', __name__, url_prefix='/badges')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@badges_bp.route('/')
@login_required
@admin_required
def index():
    """Badge designer dashboard"""
    if not HAS_BADGE_DESIGNER:
        flash('Badge designer is not available. Required packages (PIL/qrcode) may not be installed.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    templates = BadgeDesigner.get_available_templates()
    events = Event.query.filter_by(is_active=True).all()
    
    # Get some sample delegates for preview
    sample_delegates = Delegate.query.limit(5).all()
    
    return render_template('badges/index.html',
        templates=templates,
        events=events,
        sample_delegates=sample_delegates
    )


@badges_bp.route('/preview')
@login_required
@admin_required
def preview_badge():
    """Preview a badge with sample data"""
    template = request.args.get('template', 'standard')
    event_id = request.args.get('event_id', type=int)
    delegate_id = request.args.get('delegate_id', type=int)
    
    # Get event for branding
    event = Event.query.get(event_id) if event_id else None
    
    # Get delegate or create sample
    if delegate_id:
        delegate = Delegate.query.get(delegate_id)
    else:
        # Create a mock delegate for preview
        class MockDelegate:
            id = 0
            name = "John Doe"
            delegate_category = "Youth"
            parish = "St. Mary's Parish"
            archdeaconry = "Central Archdeaconry"
            delegate_number = "DEL-001"
            ticket_number = "TKT-001"
        delegate = MockDelegate()
    
    # Get custom colors from request
    colors = {}
    if request.args.get('primary_color'):
        colors['primary'] = request.args.get('primary_color')
    if request.args.get('secondary_color'):
        colors['secondary'] = request.args.get('secondary_color')
    
    # Create badge
    designer = BadgeDesigner(colors=colors)
    badge_img = designer.create_badge(delegate, event, template=template)
    
    # Convert to base64 for display
    badge_base64 = designer.badge_to_base64(badge_img)
    
    return jsonify({
        'image': f'data:image/png;base64,{badge_base64}',
        'template': template
    })


@badges_bp.route('/generate/<int:delegate_id>')
@login_required
@admin_required
def generate_badge(delegate_id):
    """Generate and download badge for a single delegate"""
    delegate = Delegate.query.get_or_404(delegate_id)
    template = request.args.get('template', 'standard')
    
    # Get event
    event = delegate.event if delegate.event_id else None
    
    # Create badge
    designer = BadgeDesigner()
    badge_img = designer.create_badge(delegate, event, template=template)
    
    # Convert to bytes for download
    img_bytes = designer.badge_to_bytes(badge_img)
    
    filename = f"badge_{delegate.name.replace(' ', '_')}_{delegate.id}.png"
    
    return send_file(
        img_bytes,
        mimetype='image/png',
        as_attachment=True,
        download_name=filename
    )


@badges_bp.route('/bulk-generate', methods=['POST'])
@login_required
@admin_required
def bulk_generate():
    """Generate badges for multiple delegates as a ZIP file"""
    template = request.form.get('template', 'standard')
    event_id = request.form.get('event_id', type=int)
    payment_filter = request.form.get('payment_filter', 'all')
    
    # Build query
    query = Delegate.query
    
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    if payment_filter == 'paid':
        query = query.filter_by(payment_status='paid')
    
    delegates = query.all()
    
    if not delegates:
        flash('No delegates found matching the criteria.', 'warning')
        return redirect(url_for('badges.index'))
    
    # Get event for branding
    event = Event.query.get(event_id) if event_id else None
    
    # Create ZIP file with badges
    zip_buffer = BytesIO()
    designer = BadgeDesigner()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for delegate in delegates:
            badge_img = designer.create_badge(delegate, event, template=template)
            img_bytes = designer.badge_to_bytes(badge_img)
            
            filename = f"badge_{delegate.name.replace(' ', '_')}_{delegate.id}.png"
            zip_file.writestr(filename, img_bytes.read())
    
    zip_buffer.seek(0)
    
    # Log activity
    current_user.log_activity(
        'bulk_generate_badges',
        'badge',
        None,
        new_values={'count': len(delegates), 'template': template}
    )
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'badges_{template}_{len(delegates)}.zip'
    )


@badges_bp.route('/print/<int:delegate_id>')
@login_required
@admin_required  
def print_badge(delegate_id):
    """Print-ready badge page"""
    delegate = Delegate.query.get_or_404(delegate_id)
    template = request.args.get('template', 'standard')
    
    event = delegate.event if delegate.event_id else None
    
    designer = BadgeDesigner()
    badge_img = designer.create_badge(delegate, event, template=template)
    badge_base64 = designer.badge_to_base64(badge_img)
    
    return render_template('badges/print.html',
        delegate=delegate,
        badge_image=f'data:image/png;base64,{badge_base64}'
    )


@badges_bp.route('/bulk-print', methods=['POST'])
@login_required
@admin_required
def bulk_print():
    """Print multiple badges on a single page"""
    delegate_ids = request.form.getlist('delegate_ids')
    template = request.form.get('template', 'standard')
    
    if not delegate_ids:
        flash('No delegates selected for printing.', 'warning')
        return redirect(url_for('badges.index'))
    
    delegates = Delegate.query.filter(Delegate.id.in_(delegate_ids)).all()
    
    designer = BadgeDesigner()
    badges = []
    
    for delegate in delegates:
        event = delegate.event if delegate.event_id else None
        badge_img = designer.create_badge(delegate, event, template=template)
        badge_base64 = designer.badge_to_base64(badge_img)
        badges.append({
            'delegate': delegate,
            'image': f'data:image/png;base64,{badge_base64}'
        })
    
    return render_template('badges/bulk_print.html', badges=badges)
