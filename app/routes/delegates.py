from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.delegate import Delegate
from app.models.user import User
from app.forms import DelegateForm, BulkRegistrationForm, SearchForm
import csv
import io

delegates_bp = Blueprint('delegates', __name__, url_prefix='/delegates')


def can_manage_delegate(delegate):
    """
    Check if current user can manage (edit/delete) a delegate.
    - Admins can manage all delegates
    - Chairs can only manage their own delegates
    """
    # Admins have full access
    if current_user.is_admin():
        return True
    
    # Own delegates (for chairs)
    if delegate.registered_by == current_user.id:
        return True
    
    return False


def can_view_delegate(delegate):
    """
    Check if current user can view a delegate.
    - Admins can view all delegates
    - Chairs can only view their own delegates
    """
    # Admins have full access
    if current_user.is_admin():
        return True
    
    # Own delegates
    if delegate.registered_by == current_user.id:
        return True
    
    return False


@delegates_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_delegate():
    form = DelegateForm()
    
    # Pre-fill with user's church details
    if request.method == 'GET':
        form.local_church.data = current_user.local_church or ''
        form.parish.data = current_user.parish or ''
        form.archdeaconry.data = current_user.archdeaconry or ''
    
    if form.validate_on_submit():
        # Check for duplicates
        duplicates = Delegate.check_duplicate(
            phone_number=form.phone_number.data,
            id_number=form.id_number.data
        )
        if duplicates:
            for msg in duplicates:
                flash(msg, 'warning')
        
        delegate = Delegate(
            ticket_number=Delegate.generate_ticket_number(),
            name=form.name.data,
            local_church=form.local_church.data,
            parish=form.parish.data,
            archdeaconry=form.archdeaconry.data,
            phone_number=form.phone_number.data or None,
            id_number=form.id_number.data or None,
            gender=form.gender.data,
            age_bracket=form.age_bracket.data,
            category=form.category.data,
            registered_by=current_user.id
        )
        
        # Auto-mark fee-exempt categories as paid
        if delegate.is_fee_exempt():
            delegate.is_paid = True
            delegate.amount_paid = 0
            delegate.payment_confirmed_by = current_user.id
            delegate.payment_confirmed_at = datetime.utcnow()
        
        db.session.add(delegate)
        db.session.commit()
        
        success_msg = f'Delegate "{delegate.name}" registered successfully! Ticket: {delegate.ticket_number}'
        if delegate.is_fee_exempt():
            success_msg += ' (Fee-exempt: No payment required)'
        flash(success_msg, 'success')
        return redirect(url_for('delegates.view_delegate', id=delegate.id))
    
    return render_template('delegates/register.html', form=form)


@delegates_bp.route('/')
@login_required
def list_delegates():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Users see only their own delegates
    delegates = Delegate.query.filter_by(
        registered_by=current_user.id
    ).order_by(Delegate.registered_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('delegates/list.html', delegates=delegates)


@delegates_bp.route('/<int:id>')
@login_required
def view_delegate(id):
    delegate = Delegate.query.get_or_404(id)
    
    # Check view permission using helper function
    if not can_view_delegate(delegate):
        flash('You do not have permission to view this delegate.', 'danger')
        return redirect(url_for('delegates.list_delegates'))
    
    # Pass whether user can edit
    can_edit = can_manage_delegate(delegate)
    return render_template('delegates/view.html', delegate=delegate, can_edit=can_edit)


@delegates_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_delegate(id):
    delegate = Delegate.query.get_or_404(id)
    
    # Check permission using helper function
    if not can_manage_delegate(delegate):
        flash('You do not have permission to edit this delegate.', 'danger')
        return redirect(url_for('delegates.list_delegates'))
    
    # Don't allow editing paid delegates
    if delegate.is_paid:
        flash('Cannot edit delegate after payment has been made.', 'warning')
        return redirect(url_for('delegates.view_delegate', id=id))
    
    form = DelegateForm(obj=delegate)
    
    if form.validate_on_submit():
        # Check for duplicates (excluding current delegate)
        duplicates = Delegate.check_duplicate(
            phone_number=form.phone_number.data,
            id_number=form.id_number.data,
            exclude_id=delegate.id
        )
        if duplicates:
            for msg in duplicates:
                flash(msg, 'warning')
        
        delegate.name = form.name.data
        delegate.local_church = form.local_church.data
        delegate.parish = form.parish.data
        delegate.archdeaconry = form.archdeaconry.data
        delegate.phone_number = form.phone_number.data or None
        delegate.id_number = form.id_number.data or None
        delegate.gender = form.gender.data
        delegate.category = form.category.data
        db.session.commit()
        flash('Delegate updated successfully!', 'success')
        return redirect(url_for('delegates.view_delegate', id=id))
    
    return render_template('delegates/edit.html', form=form, delegate=delegate)


@delegates_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_delegate(id):
    delegate = Delegate.query.get_or_404(id)
    
    # Check permission using helper function
    if not can_manage_delegate(delegate):
        flash('You do not have permission to delete this delegate.', 'danger')
        return redirect(url_for('delegates.list_delegates'))
    
    # Don't allow deleting paid delegates
    if delegate.is_paid:
        flash('Cannot delete delegate after payment has been made.', 'warning')
        return redirect(url_for('delegates.view_delegate', id=id))
    
    name = delegate.name
    db.session.delete(delegate)
    db.session.commit()
    flash(f'Delegate "{name}" has been deleted.', 'success')
    return redirect(url_for('delegates.list_delegates'))


@delegates_bp.route('/<int:id>/ticket')
@login_required
def view_ticket(id):
    """View delegate ticket with QR code"""
    delegate = Delegate.query.get_or_404(id)
    
    # Check view permission using helper function
    if not can_view_delegate(delegate):
        flash('You do not have permission to view this ticket.', 'danger')
        return redirect(url_for('delegates.list_delegates'))
    
    qr_code = delegate.generate_qr_code()
    return render_template('delegates/ticket.html', delegate=delegate, qr_code=qr_code)


@delegates_bp.route('/<int:id>/badge')
@login_required
def print_badge(id):
    """Print delegate badge"""
    delegate = Delegate.query.get_or_404(id)
    
    # Check view permission using helper function
    if not can_view_delegate(delegate):
        flash('You do not have permission to print this badge.', 'danger')
        return redirect(url_for('delegates.list_delegates'))
    
    qr_code = delegate.generate_qr_code()
    return render_template('delegates/badge.html', delegate=delegate, qr_code=qr_code)


@delegates_bp.route('/bulk', methods=['GET', 'POST'])
@login_required
def bulk_register():
    """Bulk registration via CSV upload"""
    form = BulkRegistrationForm()
    
    if form.validate_on_submit():
        file = form.csv_file.data
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        registered = 0
        errors = []
        
        for row in csv_reader:
            try:
                # Check for required fields
                name = row.get('name', '').strip()
                if not name:
                    errors.append(f"Row {registered + 1}: Missing name")
                    continue
                
                delegate = Delegate(
                    ticket_number=Delegate.generate_ticket_number(),
                    name=name,
                    local_church=row.get('local_church', current_user.local_church or ''),
                    parish=row.get('parish', current_user.parish or ''),
                    archdeaconry=row.get('archdeaconry', current_user.archdeaconry or ''),
                    phone_number=row.get('phone_number') or None,
                    id_number=row.get('id_number') or None,
                    gender=row.get('gender', 'male').lower(),
                    category=row.get('category', 'delegate').lower(),
                    registered_by=current_user.id
                )
                db.session.add(delegate)
                registered += 1
            except Exception as e:
                errors.append(f"Row {registered + 1}: {str(e)}")
        
        db.session.commit()
        
        if registered > 0:
            flash(f'Successfully registered {registered} delegates!', 'success')
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                flash(error, 'warning')
            if len(errors) > 5:
                flash(f'... and {len(errors) - 5} more errors', 'warning')
        
        return redirect(url_for('delegates.list_delegates'))
    
    return render_template('delegates/bulk.html', form=form)


@delegates_bp.route('/bulk/template')
@login_required
def download_template():
    """Download CSV template for bulk registration"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'phone_number', 'id_number', 'gender', 'category', 'local_church', 'parish', 'archdeaconry'])
    writer.writerow(['John Doe', '0712345678', '12345678', 'male', 'delegate', 'St. Peters', 'Sample Parish', 'Sample Archdeaconry'])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=delegate_template.csv'}
    )


@delegates_bp.route('/export')
@login_required
def export_delegates():
    """Export delegates to Excel/CSV format"""
    from app.models.event import Event
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    event_id = request.args.get('event_id')
    format_type = request.args.get('format', 'csv')
    
    # Build query based on user role
    if current_user.is_admin():
        query = Delegate.query
    else:
        query = Delegate.query.filter_by(registered_by=current_user.id)
    
    # Apply filters
    if status != 'all':
        query = query.filter_by(registration_status=status)
    if event_id:
        query = query.filter_by(event_id=event_id)
    
    delegates = query.order_by(Delegate.created_at.desc()).all()
    
    # Create CSV output
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'ID', 'Full Name', 'Phone', 'Email', 'ID Number', 'Gender', 'Age Bracket',
        'Category', 'Local Church', 'Parish', 'Archdeaconry',
        'Registration Status', 'Payment Status', 'Amount Paid',
        'Checked In', 'Registered By', 'Registration Date'
    ])
    
    # Data rows
    for d in delegates:
        registered_by = User.query.get(d.registered_by)
        writer.writerow([
            d.id,
            d.full_name,
            d.phone or '',
            d.email or '',
            d.id_number or '',
            d.gender or '',
            d.age_bracket or '',
            d.category or '',
            d.local_church or '',
            d.parish or '',
            d.archdeaconry or '',
            d.registration_status,
            d.payment_status,
            d.amount_paid or 0,
            'Yes' if d.checked_in else 'No',
            registered_by.name if registered_by else '',
            d.created_at.strftime('%Y-%m-%d %H:%M') if d.created_at else ''
        ])
    
    output.seek(0)
    
    filename = f'delegates_export_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@delegates_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_delegates():
    """Batch import delegates from CSV/Excel file"""
    if request.method == 'GET':
        return render_template('delegates/import.html')
    
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('delegates.import_delegates'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('delegates.import_delegates'))
    
    # Check file extension
    if not file.filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        flash('Invalid file format. Please upload CSV or Excel file.', 'error')
        return redirect(url_for('delegates.import_delegates'))
    
    try:
        if file.filename.lower().endswith('.csv'):
            # Parse CSV
            content = file.read().decode('utf-8-sig')  # Handle BOM
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
        else:
            # Parse Excel
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file)
                ws = wb.active
                headers = [cell.value for cell in ws[1]]
                rows = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    row_dict = dict(zip(headers, row))
                    rows.append(row_dict)
            except ImportError:
                flash('Excel support requires openpyxl. Please use CSV format.', 'error')
                return redirect(url_for('delegates.import_delegates'))
        
        # Process rows
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, row in enumerate(rows, start=2):  # Start at 2 (row 1 is header)
            try:
                # Normalize column names (case-insensitive, strip whitespace)
                row = {k.strip().lower() if k else '': v for k, v in row.items()}
                
                # Get name (required)
                name = row.get('name') or row.get('full name') or row.get('fullname')
                if not name or str(name).strip() == '':
                    errors.append(f'Row {idx}: Name is required')
                    error_count += 1
                    continue
                
                # Get other fields with defaults
                delegate = Delegate(
                    ticket_number=Delegate.generate_ticket_number(),
                    name=str(name).strip(),
                    phone_number=str(row.get('phone') or row.get('phone number') or row.get('phone_number') or '').strip() or None,
                    id_number=str(row.get('id number') or row.get('id_number') or row.get('id') or '').strip() or None,
                    gender=str(row.get('gender') or '').strip().lower() or 'male',
                    age_bracket=str(row.get('age bracket') or row.get('age_bracket') or row.get('age') or '20_24').strip(),
                    category=str(row.get('category') or 'delegate').strip().lower(),
                    local_church=str(row.get('local church') or row.get('local_church') or row.get('church') or current_user.local_church or '').strip(),
                    parish=str(row.get('parish') or current_user.parish or '').strip(),
                    archdeaconry=str(row.get('archdeaconry') or current_user.archdeaconry or '').strip(),
                    registered_by=current_user.id
                )
                
                # Auto-mark fee-exempt categories as paid
                if delegate.is_fee_exempt():
                    delegate.is_paid = True
                    delegate.amount_paid = 0
                    delegate.payment_confirmed_by = current_user.id
                    delegate.payment_confirmed_at = datetime.utcnow()
                
                db.session.add(delegate)
                success_count += 1
                
            except Exception as e:
                errors.append(f'Row {idx}: {str(e)}')
                error_count += 1
        
        db.session.commit()
        
        if success_count > 0:
            flash(f'Successfully imported {success_count} delegate(s)!', 'success')
        if error_count > 0:
            flash(f'Failed to import {error_count} row(s). See details below.', 'warning')
            for error in errors[:5]:  # Show first 5 errors
                flash(error, 'error')
        
        return redirect(url_for('delegates.list_delegates'))
        
    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('delegates.import_delegates'))


@delegates_bp.route('/import/template')
@login_required
def download_import_template():
    """Download a CSV template for batch import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'name', 'phone', 'gender', 'age bracket', 'category',
        'local church', 'parish', 'archdeaconry'
    ])
    
    # Sample rows
    writer.writerow([
        'John Doe', '0712345678', 'male', '20_24', 'delegate',
        'St. Paul Church', 'Nambale Parish', 'Nambale Archdeaconry'
    ])
    writer.writerow([
        'Jane Smith', '0723456789', 'female', '15_19', 'leader',
        '', '', ''  # Will use user's default church
    ])
    writer.writerow([
        'Mary Johnson', '', 'female', '25_29', 'counsellor',
        '', '', ''
    ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=delegates_import_template.csv'}
    )
