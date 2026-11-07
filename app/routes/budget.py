"""
Budget Management Routes
Upload, parse, and track budget implementation
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os

from app import db
from app.models.user import User
from app.models.budget import Budget, BudgetItem, BudgetExpenditure, BudgetParser

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')


def admin_required(f):
    """Decorator to require admin or super_admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role not in ['admin', 'super_admin', 'finance']:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@budget_bp.route('/')
@login_required
@admin_required
def index():
    """List all budgets"""
    budgets = Budget.query.order_by(Budget.created_at.desc()).all()
    return render_template('budget/index.html', budgets=budgets)


@budget_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    """Create a new budget manually or upload file"""
    from app.models.event import Event
    events = Event.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        event_id = request.form.get('event_id') or None
        
        if not name:
            flash('Budget name is required.', 'danger')
            return redirect(url_for('budget.create'))
        
        budget = Budget(
            name=name,
            description=description,
            event_id=event_id,
            created_by=current_user.id,
            status='draft'
        )
        
        db.session.add(budget)
        db.session.commit()
        
        flash(f'Budget "{name}" created successfully. Now add items or upload a file.', 'success')
        return redirect(url_for('budget.view', id=budget.id))
    
    return render_template('budget/create.html', events=events)


@budget_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload():
    """Upload and parse a budget file"""
    from app.models.event import Event
    events = Event.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        event_id = request.form.get('event_id') or None
        
        if not name:
            flash('Budget name is required.', 'danger')
            return redirect(url_for('budget.upload'))
        
        if 'budget_file' not in request.files:
            flash('Please select a file to upload.', 'danger')
            return redirect(url_for('budget.upload'))
        
        file = request.files['budget_file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('budget.upload'))
        
        # Check file extension
        filename = file.filename
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        if ext not in ['csv', 'xlsx', 'xls', 'txt']:
            flash('Unsupported file format. Please upload CSV, Excel, or text file.', 'danger')
            return redirect(url_for('budget.upload'))
        
        try:
            # Read file content
            file_content = file.read()
            
            # Parse based on file type
            items = []
            raw_content = ''
            
            if ext == 'csv':
                raw_content = file_content.decode('utf-8', errors='ignore')
                items = BudgetParser.parse_csv(raw_content)
            elif ext in ['xlsx', 'xls']:
                items = BudgetParser.parse_excel(file_content)
                raw_content = f"Excel file: {filename}"
            elif ext == 'txt':
                raw_content = file_content.decode('utf-8', errors='ignore')
                items = BudgetParser.parse_text(raw_content)
            
            if not items:
                flash('No budget items could be extracted from the file. Please check the format.', 'warning')
                return redirect(url_for('budget.upload'))
            
            # Create budget
            budget = Budget(
                name=name,
                description=description,
                event_id=event_id,
                created_by=current_user.id,
                original_filename=filename,
                file_type=ext,
                raw_content=raw_content[:10000],  # Store first 10k chars
                status='draft'
            )
            db.session.add(budget)
            db.session.flush()  # Get budget.id
            
            # Create budget items
            total_budgeted = 0
            for item_data in items:
                item = BudgetItem(
                    budget_id=budget.id,
                    item_number=item_data.get('item_number', 0),
                    category=item_data.get('category', 'other'),
                    name=item_data.get('name', 'Unknown Item'),
                    description=item_data.get('description', ''),
                    quantity=item_data.get('quantity', 1),
                    unit=item_data.get('unit', ''),
                    unit_cost=item_data.get('unit_cost', 0),
                    budgeted_amount=item_data.get('budgeted_amount', 0),
                    status='pending'
                )
                db.session.add(item)
                total_budgeted += item.budgeted_amount
            
            budget.total_budgeted = total_budgeted
            db.session.commit()
            
            flash(f'Budget "{name}" created with {len(items)} items (Total: KSh {total_budgeted:,.0f}). Please review and adjust categories.', 'success')
            return redirect(url_for('budget.view', id=budget.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error parsing budget file: {str(e)}')
            flash(f'Error processing file: {str(e)}', 'danger')
            return redirect(url_for('budget.upload'))
    
    return render_template('budget/upload.html', events=events)


@budget_bp.route('/<int:id>')
@login_required
@admin_required
def view(id):
    """View budget details and items"""
    budget = Budget.query.get_or_404(id)
    
    # Group items by category
    items_by_category = {}
    for item in budget.items.order_by(BudgetItem.category, BudgetItem.item_number):
        category = item.category
        if category not in items_by_category:
            items_by_category[category] = {
                'budget_items': [],
                'total_budgeted': 0,
                'total_spent': 0
            }
        items_by_category[category]['budget_items'].append(item)
        items_by_category[category]['total_budgeted'] += item.budgeted_amount
        items_by_category[category]['total_spent'] += item.actual_spent
    
    return render_template('budget/view.html', 
                         budget=budget, 
                         items_by_category=items_by_category,
                         categories=dict(BudgetItem.CATEGORIES))


@budget_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Edit budget details"""
    budget = Budget.query.get_or_404(id)
    from app.models.event import Event
    events = Event.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        budget.name = request.form.get('name', budget.name)
        budget.description = request.form.get('description')
        budget.event_id = request.form.get('event_id') or None
        budget.status = request.form.get('status', budget.status)
        
        db.session.commit()
        flash('Budget updated successfully.', 'success')
        return redirect(url_for('budget.view', id=budget.id))
    
    return render_template('budget/edit.html', budget=budget, events=events)


@budget_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete a budget"""
    budget = Budget.query.get_or_404(id)
    
    if budget.status == 'active' and budget.total_spent > 0:
        flash('Cannot delete an active budget with recorded expenditures.', 'danger')
        return redirect(url_for('budget.view', id=id))
    
    name = budget.name
    db.session.delete(budget)
    db.session.commit()
    
    flash(f'Budget "{name}" deleted successfully.', 'success')
    return redirect(url_for('budget.index'))


@budget_bp.route('/<int:id>/activate', methods=['POST'])
@login_required
@admin_required
def activate(id):
    """Activate a budget for tracking"""
    budget = Budget.query.get_or_404(id)
    
    if budget.items.count() == 0:
        flash('Cannot activate a budget with no items.', 'danger')
        return redirect(url_for('budget.view', id=id))
    
    budget.status = 'active'
    budget.approved_by = current_user.id
    budget.approved_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'Budget "{budget.name}" is now active. You can start recording expenditures.', 'success')
    return redirect(url_for('budget.view', id=id))


# Budget Item Routes
@budget_bp.route('/<int:budget_id>/item/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_item(budget_id):
    """Add a new item to budget"""
    budget = Budget.query.get_or_404(budget_id)
    
    if request.method == 'POST':
        item = BudgetItem(
            budget_id=budget_id,
            item_number=budget.items.count() + 1,
            category=request.form.get('category', 'other'),
            name=request.form.get('name'),
            description=request.form.get('description'),
            quantity=float(request.form.get('quantity', 1)),
            unit=request.form.get('unit'),
            unit_cost=float(request.form.get('unit_cost', 0)),
            budgeted_amount=float(request.form.get('budgeted_amount', 0)),
            priority=request.form.get('priority', 'medium'),
            assigned_to=request.form.get('assigned_to'),
            status='pending'
        )
        
        # Calculate amount if not provided
        if item.budgeted_amount == 0 and item.quantity > 0 and item.unit_cost > 0:
            item.budgeted_amount = item.quantity * item.unit_cost
        
        db.session.add(item)
        budget.update_totals()
        db.session.commit()
        
        flash(f'Item "{item.name}" added to budget.', 'success')
        return redirect(url_for('budget.view', id=budget_id))
    
    return render_template('budget/add_item.html', budget=budget, categories=BudgetItem.CATEGORIES)


@budget_bp.route('/item/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_item(id):
    """Edit a budget item"""
    item = BudgetItem.query.get_or_404(id)
    
    if request.method == 'POST':
        item.category = request.form.get('category', item.category)
        item.name = request.form.get('name', item.name)
        item.description = request.form.get('description')
        item.quantity = float(request.form.get('quantity', item.quantity))
        item.unit = request.form.get('unit')
        item.unit_cost = float(request.form.get('unit_cost', item.unit_cost))
        item.budgeted_amount = float(request.form.get('budgeted_amount', item.budgeted_amount))
        item.priority = request.form.get('priority', item.priority)
        item.assigned_to = request.form.get('assigned_to')
        item.status = request.form.get('status', item.status)
        item.notes = request.form.get('notes')
        
        if item.status == 'completed' and not item.completed_at:
            item.completed_at = datetime.utcnow()
        
        item.budget.update_totals()
        db.session.commit()
        
        flash(f'Item "{item.name}" updated.', 'success')
        return redirect(url_for('budget.view', id=item.budget_id))
    
    return render_template('budget/edit_item.html', item=item, categories=BudgetItem.CATEGORIES)


@budget_bp.route('/item/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_item(id):
    """Delete a budget item"""
    item = BudgetItem.query.get_or_404(id)
    budget_id = item.budget_id
    
    if item.actual_spent > 0:
        flash('Cannot delete an item with recorded expenditures.', 'danger')
        return redirect(url_for('budget.view', id=budget_id))
    
    name = item.name
    budget = item.budget
    db.session.delete(item)
    budget.update_totals()
    db.session.commit()
    
    flash(f'Item "{name}" deleted.', 'success')
    return redirect(url_for('budget.view', id=budget_id))


# Expenditure Routes
@budget_bp.route('/item/<int:item_id>/expenditure/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_expenditure(item_id):
    """Record an expenditure against a budget item"""
    item = BudgetItem.query.get_or_404(item_id)
    
    if item.budget.status != 'active':
        flash('Cannot record expenditures on an inactive budget.', 'danger')
        return redirect(url_for('budget.view', id=item.budget_id))
    
    if request.method == 'POST':
        expenditure = BudgetExpenditure(
            budget_item_id=item_id,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            description=request.form.get('description'),
            amount=float(request.form.get('amount', 0)),
            payment_method=request.form.get('payment_method'),
            reference_number=request.form.get('reference_number'),
            vendor=request.form.get('vendor'),
            recorded_by=current_user.id,
            status='approved' if current_user.role in ['admin', 'super_admin'] else 'pending'
        )
        
        # Auto-approve for admins
        if expenditure.status == 'approved':
            expenditure.approved_by = current_user.id
            expenditure.approved_at = datetime.utcnow()
        
        db.session.add(expenditure)
        item.update_actual_spent()
        
        # Update item status if spending started
        if item.status == 'pending':
            item.status = 'in_progress'
        
        db.session.commit()
        
        flash(f'Expenditure of KSh {expenditure.amount:,.0f} recorded.', 'success')
        return redirect(url_for('budget.view', id=item.budget_id))
    
    return render_template('budget/add_expenditure.html', item=item)


@budget_bp.route('/expenditure/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_expenditure(id):
    """Approve an expenditure"""
    expenditure = BudgetExpenditure.query.get_or_404(id)
    
    expenditure.status = 'approved'
    expenditure.approved_by = current_user.id
    expenditure.approved_at = datetime.utcnow()
    
    expenditure.budget_item.update_actual_spent()
    db.session.commit()
    
    flash('Expenditure approved.', 'success')
    return redirect(url_for('budget.view', id=expenditure.budget_item.budget_id))


@budget_bp.route('/expenditure/<int:id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_expenditure(id):
    """Reject an expenditure"""
    expenditure = BudgetExpenditure.query.get_or_404(id)
    
    expenditure.status = 'rejected'
    expenditure.rejection_reason = request.form.get('reason', 'Rejected by admin')
    
    expenditure.budget_item.update_actual_spent()
    db.session.commit()
    
    flash('Expenditure rejected.', 'info')
    return redirect(url_for('budget.view', id=expenditure.budget_item.budget_id))


# API endpoints for AJAX
@budget_bp.route('/api/item/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def update_item_status(id):
    """Update item status via AJAX"""
    item = BudgetItem.query.get_or_404(id)
    data = request.get_json()
    
    item.status = data.get('status', item.status)
    if item.status == 'completed' and not item.completed_at:
        item.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'status': item.status})


@budget_bp.route('/api/parse-preview', methods=['POST'])
@login_required
@admin_required
def parse_preview():
    """Preview parsed budget items without saving"""
    if 'budget_file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['budget_file']
    filename = file.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    try:
        file_content = file.read()
        items = []
        
        if ext == 'csv':
            raw_content = file_content.decode('utf-8', errors='ignore')
            items = BudgetParser.parse_csv(raw_content)
        elif ext in ['xlsx', 'xls']:
            items = BudgetParser.parse_excel(file_content)
        elif ext == 'txt':
            raw_content = file_content.decode('utf-8', errors='ignore')
            items = BudgetParser.parse_text(raw_content)
        
        total = sum(item.get('budgeted_amount', 0) for item in items)
        
        return jsonify({
            'success': True,
            'items': items,
            'count': len(items),
            'total': total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Reports
@budget_bp.route('/<int:id>/report')
@login_required
@admin_required
def report(id):
    """Generate budget implementation report"""
    budget = Budget.query.get_or_404(id)
    
    # Calculate statistics
    stats = {
        'total_items': budget.items.count(),
        'completed_items': budget.items.filter_by(status='completed').count(),
        'in_progress_items': budget.items.filter_by(status='in_progress').count(),
        'pending_items': budget.items.filter_by(status='pending').count(),
        'total_budgeted': budget.total_budgeted,
        'total_spent': budget.total_spent,
        'balance': budget.balance_remaining,
        'utilization': budget.utilization_percentage
    }
    
    # Category breakdown
    category_stats = {}
    for item in budget.items:
        cat = item.category
        if cat not in category_stats:
            category_stats[cat] = {'budgeted': 0, 'spent': 0, 'item_count': 0}
        category_stats[cat]['budgeted'] += item.budgeted_amount
        category_stats[cat]['spent'] += item.actual_spent
        category_stats[cat]['item_count'] += 1
    
    return render_template('budget/report.html', 
                         budget=budget, 
                         stats=stats, 
                         category_stats=category_stats,
                         categories=dict(BudgetItem.CATEGORIES))
