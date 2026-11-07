"""
Finance Routes - Professional Financial Management System
Handles vouchers, journals, statements, balance sheets, and reports
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, Response
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from decimal import Decimal
import csv
from io import StringIO
from app import db
from app.models.finance import (
    AccountCategory, Account, JournalEntry, JournalLine,
    Voucher, VoucherItem, FinancialPeriod, BudgetLine
)
from app.models.payment import Payment
from app.models.delegate import Delegate

finance_bp = Blueprint('finance', __name__, url_prefix='/finance')

# Allowed roles for finance operations
FINANCE_ROLES = ['finance', 'treasurer', 'admin', 'super_admin']


def require_finance_role(f):
    """Decorator to require finance role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in FINANCE_ROLES:
            flash('Access denied. Finance personnel only.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== DASHBOARD ====================

@finance_bp.route('/')
@login_required
@require_finance_role
def dashboard():
    """Finance Dashboard - Overview of financial status"""
    today = date.today()
    month_start = today.replace(day=1)
    
    # Get key metrics
    total_income = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.status == 'completed'
    ).scalar() or 0
    
    # Get voucher stats
    pending_vouchers = Voucher.query.filter_by(status='pending_approval').count()
    draft_vouchers = Voucher.query.filter_by(status='draft').count()
    
    # Get pending payment approvals count
    pending_payment_approvals = Payment.query.filter(
        Payment.finance_status == 'pending_approval'
    ).count()
    
    # Recent transactions
    recent_vouchers = Voucher.query.order_by(Voucher.created_at.desc()).limit(5).all()
    recent_journals = JournalEntry.query.order_by(JournalEntry.created_at.desc()).limit(5).all()
    
    # Account summaries by type
    account_summaries = db.session.query(
        Account.account_type,
        db.func.sum(Account.current_balance).label('total')
    ).filter(Account.is_active == True).group_by(Account.account_type).all()
    
    summaries = {s.account_type: s.total or 0 for s in account_summaries}
    
    # Delegate payment stats
    total_delegates = Delegate.query.count()
    paid_delegates = Delegate.query.filter_by(is_paid=True).count()
    delegate_fee = current_app.config.get('DELEGATE_FEE', 500)
    expected_income = total_delegates * delegate_fee
    collection_rate = (total_income / expected_income * 100) if expected_income > 0 else 0
    
    return render_template('finance/dashboard.html',
        total_income=total_income,
        expected_income=expected_income,
        collection_rate=collection_rate,
        pending_vouchers=pending_vouchers,
        draft_vouchers=draft_vouchers,
        pending_payment_approvals=pending_payment_approvals,
        recent_vouchers=recent_vouchers,
        recent_journals=recent_journals,
        summaries=summaries,
        total_delegates=total_delegates,
        paid_delegates=paid_delegates
    )


# ==================== CHART OF ACCOUNTS ====================

@finance_bp.route('/accounts')
@login_required
@require_finance_role
def chart_of_accounts():
    """View chart of accounts"""
    categories = AccountCategory.query.order_by(AccountCategory.code).all()
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    
    # Group accounts by type
    accounts_by_type = {}
    for account in accounts:
        if account.account_type not in accounts_by_type:
            accounts_by_type[account.account_type] = []
        accounts_by_type[account.account_type].append(account)
    
    return render_template('finance/chart_of_accounts.html',
        categories=categories,
        accounts=accounts,
        accounts_by_type=accounts_by_type
    )


@finance_bp.route('/accounts/create', methods=['GET', 'POST'])
@login_required
@require_finance_role
def create_account():
    """Create a new account"""
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        account_type = request.form.get('account_type')
        category_id = request.form.get('category_id')
        description = request.form.get('description')
        opening_balance = float(request.form.get('opening_balance', 0))
        
        # Determine normal balance
        normal_balance = 'debit' if account_type in ['asset', 'expense'] else 'credit'
        
        # Check if code exists
        if Account.query.filter_by(code=code).first():
            flash('Account code already exists.', 'danger')
            return redirect(url_for('finance.create_account'))
        
        account = Account(
            code=code,
            name=name,
            account_type=account_type,
            category_id=category_id,
            normal_balance=normal_balance,
            description=description,
            opening_balance=opening_balance,
            current_balance=opening_balance
        )
        db.session.add(account)
        db.session.commit()
        
        flash(f'Account "{name}" created successfully.', 'success')
        return redirect(url_for('finance.chart_of_accounts'))
    
    categories = AccountCategory.query.order_by(AccountCategory.code).all()
    return render_template('finance/create_account.html', categories=categories)


@finance_bp.route('/accounts/<int:account_id>/ledger')
@login_required
@require_finance_role
def account_ledger(account_id):
    """View account ledger/transactions"""
    account = Account.query.get_or_404(account_id)
    
    # Get all journal lines for this account
    lines = JournalLine.query.filter_by(account_id=account_id)\
        .join(JournalEntry).filter(JournalEntry.status == 'posted')\
        .order_by(JournalEntry.date.asc(), JournalEntry.id.asc()).all()
    
    # Build transactions list with running balance
    transactions = []
    total_debits = 0
    total_credits = 0
    
    for line in lines:
        total_debits += line.debit or 0
        total_credits += line.credit or 0
        transactions.append({
            'date': line.journal_entry.date,
            'entry_id': line.journal_entry.id,
            'entry_number': line.journal_entry.entry_number,
            'description': line.description or line.journal_entry.description,
            'reference': line.journal_entry.reference,
            'debit': line.debit or 0,
            'credit': line.credit or 0
        })
    
    return render_template('finance/account_ledger.html',
        account=account,
        transactions=transactions,
        total_debits=total_debits,
        total_credits=total_credits,
        opening_balance=account.opening_balance
    )


# ==================== VOUCHERS ====================

@finance_bp.route('/vouchers')
@login_required
@require_finance_role
def list_vouchers():
    """List all vouchers"""
    voucher_type = request.args.get('type', '')
    status = request.args.get('status', '')
    
    query = Voucher.query
    if voucher_type:
        query = query.filter_by(voucher_type=voucher_type)
    if status:
        query = query.filter_by(status=status)
    
    vouchers = query.order_by(Voucher.created_at.desc()).all()
    
    # Stats
    stats = {
        'total': Voucher.query.count(),
        'draft': Voucher.query.filter_by(status='draft').count(),
        'pending': Voucher.query.filter_by(status='pending_approval').count(),
        'approved': Voucher.query.filter_by(status='approved').count(),
        'paid': Voucher.query.filter_by(status='paid').count()
    }
    
    return render_template('finance/vouchers_list.html',
        vouchers=vouchers,
        stats=stats,
        current_type=voucher_type,
        current_status=status
    )


@finance_bp.route('/vouchers/create', methods=['GET', 'POST'])
@finance_bp.route('/vouchers/create/<voucher_type>', methods=['GET', 'POST'])
@login_required
@require_finance_role
def create_voucher(voucher_type='payment'):
    """Create a new voucher"""
    if request.method == 'POST':
        voucher_type = request.form.get('voucher_type', 'payment')
        
        voucher = Voucher(
            voucher_number=Voucher.generate_voucher_number(voucher_type),
            voucher_type=voucher_type,
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            payee_name=request.form.get('payee_name'),
            payee_type=request.form.get('payee_type'),
            amount=float(request.form.get('amount', 0)),
            amount_in_words=request.form.get('amount_in_words'),
            payment_method=request.form.get('payment_method'),
            reference_number=request.form.get('reference_number'),
            bank_name=request.form.get('bank_name'),
            narration=request.form.get('narration'),
            category=request.form.get('category'),
            prepared_by=current_user.id,
            status='draft'
        )
        db.session.add(voucher)
        db.session.flush()
        
        # Add line items
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_prices = request.form.getlist('item_unit_price[]')
        amounts = request.form.getlist('item_amount[]')
        account_ids = request.form.getlist('item_account_id[]')
        
        total_amount = 0
        for i in range(len(descriptions)):
            if descriptions[i]:
                amount = float(amounts[i]) if amounts[i] else 0
                item = VoucherItem(
                    voucher_id=voucher.id,
                    description=descriptions[i],
                    quantity=float(quantities[i]) if quantities[i] else 1,
                    unit_price=float(unit_prices[i]) if unit_prices[i] else 0,
                    amount=amount,
                    account_id=int(account_ids[i]) if account_ids[i] else None
                )
                db.session.add(item)
                total_amount += amount
        
        voucher.amount = total_amount
        db.session.commit()
        
        flash(f'Voucher {voucher.voucher_number} created successfully.', 'success')
        return redirect(url_for('finance.view_voucher', voucher_id=voucher.id))
    
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    expense_accounts = [a for a in accounts if a.account_type == 'expense']
    income_accounts = [a for a in accounts if a.account_type == 'income']
    
    return render_template('finance/create_voucher.html',
        voucher_type=voucher_type,
        accounts=accounts,
        expense_accounts=expense_accounts,
        income_accounts=income_accounts,
        today=date.today()
    )


@finance_bp.route('/vouchers/<int:voucher_id>')
@login_required
@require_finance_role
def view_voucher(voucher_id):
    """View voucher details"""
    voucher = Voucher.query.get_or_404(voucher_id)
    return render_template('finance/view_voucher.html', voucher=voucher)


@finance_bp.route('/vouchers/<int:voucher_id>/submit', methods=['POST'])
@login_required
@require_finance_role
def submit_voucher(voucher_id):
    """Submit voucher for approval"""
    voucher = Voucher.query.get_or_404(voucher_id)
    
    if voucher.status != 'draft':
        flash('Only draft vouchers can be submitted.', 'warning')
        return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))
    
    voucher.status = 'pending_approval'
    db.session.commit()
    
    flash(f'Voucher {voucher.voucher_number} submitted for approval.', 'success')
    return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))


@finance_bp.route('/vouchers/<int:voucher_id>/approve', methods=['POST'])
@login_required
@require_finance_role
def approve_voucher(voucher_id):
    """Approve a voucher"""
    voucher = Voucher.query.get_or_404(voucher_id)
    
    if voucher.status != 'pending_approval':
        flash('Only pending vouchers can be approved.', 'warning')
        return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))
    
    action = request.form.get('action')
    
    if action == 'approve':
        voucher.status = 'approved'
        voucher.approved_by = current_user.id
        voucher.approved_at = datetime.utcnow()
        flash(f'Voucher {voucher.voucher_number} approved.', 'success')
    elif action == 'reject':
        voucher.status = 'draft'
        voucher.notes = f"Rejected by {current_user.name}: {request.form.get('notes', '')}"
        flash(f'Voucher {voucher.voucher_number} rejected.', 'warning')
    
    db.session.commit()
    return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))


@finance_bp.route('/vouchers/<int:voucher_id>/pay', methods=['POST'])
@login_required
@require_finance_role
def mark_voucher_paid(voucher_id):
    """Mark voucher as paid and create journal entry"""
    voucher = Voucher.query.get_or_404(voucher_id)
    
    if voucher.status != 'approved':
        flash('Only approved vouchers can be marked as paid.', 'warning')
        return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))
    
    voucher.status = 'paid'
    voucher.paid_at = datetime.utcnow()
    voucher.reference_number = request.form.get('reference_number', voucher.reference_number)
    
    # Create journal entry for this payment
    entry = JournalEntry(
        entry_number=JournalEntry.generate_entry_number(),
        date=voucher.date,
        description=f"Payment: {voucher.narration}",
        reference=voucher.voucher_number,
        entry_type='general',
        status='posted',
        created_by=current_user.id,
        posted_by=current_user.id,
        posted_at=datetime.utcnow(),
        voucher_id=voucher.id
    )
    db.session.add(entry)
    db.session.flush()
    
    # Add journal lines based on voucher items
    # Debit expense accounts
    for item in voucher.items:
        if item.account_id:
            line = JournalLine(
                entry_id=entry.id,
                account_id=item.account_id,
                description=item.description,
                debit=item.amount if voucher.voucher_type == 'payment' else 0,
                credit=item.amount if voucher.voucher_type == 'receipt' else 0
            )
            db.session.add(line)
    
    # Credit cash/bank account (need to get the cash account)
    cash_account = Account.query.filter_by(code='1001').first()  # Assuming 1001 is cash
    if cash_account:
        line = JournalLine(
            entry_id=entry.id,
            account_id=cash_account.id,
            description=f"{voucher.voucher_type.title()} - {voucher.payee_name}",
            debit=voucher.amount if voucher.voucher_type == 'receipt' else 0,
            credit=voucher.amount if voucher.voucher_type == 'payment' else 0
        )
        db.session.add(line)
    
    db.session.commit()
    
    # Update account balances
    for line in entry.lines:
        line.account.update_balance()
    db.session.commit()
    
    flash(f'Voucher {voucher.voucher_number} marked as paid. Journal entry {entry.entry_number} created.', 'success')
    return redirect(url_for('finance.view_voucher', voucher_id=voucher_id))


@finance_bp.route('/vouchers/<int:voucher_id>/print')
@login_required
@require_finance_role
def print_voucher(voucher_id):
    """Print-friendly voucher view"""
    voucher = Voucher.query.get_or_404(voucher_id)
    return render_template('finance/print_voucher.html', voucher=voucher)


# ==================== JOURNAL ENTRIES ====================

@finance_bp.route('/journals')
@login_required
@require_finance_role
def list_journals():
    """List all journal entries"""
    status = request.args.get('status', '')
    
    query = JournalEntry.query
    if status:
        query = query.filter_by(status=status)
    
    entries = query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).all()
    
    return render_template('finance/journals_list.html',
        entries=entries,
        current_status=status
    )


@finance_bp.route('/journals/create', methods=['GET', 'POST'])
@login_required
@require_finance_role
def create_journal():
    """Create a new journal entry"""
    if request.method == 'POST':
        entry = JournalEntry(
            entry_number=JournalEntry.generate_entry_number(),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            description=request.form.get('description'),
            reference=request.form.get('reference'),
            entry_type=request.form.get('entry_type', 'general'),
            created_by=current_user.id,
            status='draft'
        )
        db.session.add(entry)
        db.session.flush()
        
        # Add journal lines
        account_ids = request.form.getlist('account_id[]')
        descriptions = request.form.getlist('line_description[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        
        for i in range(len(account_ids)):
            if account_ids[i]:
                line = JournalLine(
                    entry_id=entry.id,
                    account_id=int(account_ids[i]),
                    description=descriptions[i] if i < len(descriptions) else '',
                    debit=float(debits[i]) if debits[i] else 0,
                    credit=float(credits[i]) if credits[i] else 0
                )
                db.session.add(line)
        
        db.session.commit()
        
        flash(f'Journal entry {entry.entry_number} created.', 'success')
        return redirect(url_for('finance.view_journal', entry_id=entry.id))
    
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    # Convert to list of dicts for JSON serialization in template
    accounts_data = [{'id': a.id, 'code': a.code, 'name': a.name} for a in accounts]
    return render_template('finance/create_journal.html',
        accounts=accounts_data,
        today=date.today()
    )


@finance_bp.route('/journals/<int:entry_id>')
@login_required
@require_finance_role
def view_journal(entry_id):
    """View journal entry details"""
    entry = JournalEntry.query.get_or_404(entry_id)
    return render_template('finance/view_journal.html', entry=entry)


@finance_bp.route('/journals/<int:entry_id>/post', methods=['POST'])
@login_required
@require_finance_role
def post_journal(entry_id):
    """Post a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)
    
    if entry.status != 'draft':
        flash('Only draft entries can be posted.', 'warning')
        return redirect(url_for('finance.view_journal', entry_id=entry_id))
    
    if not entry.is_balanced():
        flash('Journal entry is not balanced. Debits must equal credits.', 'danger')
        return redirect(url_for('finance.view_journal', entry_id=entry_id))
    
    try:
        entry.post(current_user.id)
        db.session.commit()
        flash(f'Journal entry {entry.entry_number} posted successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    
    return redirect(url_for('finance.view_journal', entry_id=entry_id))


@finance_bp.route('/journals/<int:entry_id>/void', methods=['POST'])
@login_required
@require_finance_role
def void_journal(entry_id):
    """Void a journal entry"""
    entry = JournalEntry.query.get_or_404(entry_id)
    
    reason = request.form.get('reason', 'No reason provided')
    entry.void(current_user.id, reason)
    db.session.commit()
    
    flash(f'Journal entry {entry.entry_number} voided.', 'warning')
    return redirect(url_for('finance.view_journal', entry_id=entry_id))


# ==================== FINANCIAL REPORTS ====================

@finance_bp.route('/reports')
@login_required
@require_finance_role
def reports_index():
    """Financial reports index"""
    return render_template('finance/reports_index.html')


@finance_bp.route('/reports/trial-balance')
@login_required
@require_finance_role
def trial_balance():
    """Generate trial balance"""
    as_of_date = request.args.get('as_of_date')
    if as_of_date:
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
    else:
        as_of_date = date.today()
    
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    
    trial_balance_data = []
    total_debit = 0
    total_credit = 0
    
    for account in accounts:
        balance = account.get_balance(as_of_date)
        if balance != 0:
            if account.normal_balance == 'debit':
                debit = balance if balance > 0 else 0
                credit = abs(balance) if balance < 0 else 0
            else:
                credit = balance if balance > 0 else 0
                debit = abs(balance) if balance < 0 else 0
            
            trial_balance_data.append({
                'account': account,
                'debit': debit,
                'credit': credit
            })
            total_debit += debit
            total_credit += credit
    
    return render_template('finance/trial_balance.html',
        trial_balance=trial_balance_data,
        total_debit=total_debit,
        total_credit=total_credit,
        as_of_date=as_of_date
    )


@finance_bp.route('/reports/income-statement')
@login_required
@require_finance_role
def income_statement():
    """Generate income statement"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()
    
    # Income accounts
    income_accounts = Account.query.filter_by(account_type='income', is_active=True).all()
    income_data = []
    total_income = 0
    
    for account in income_accounts:
        balance = account.get_balance(end_date) - account.get_balance(start_date)
        if balance != 0:
            income_data.append({'account': account, 'amount': abs(balance)})
            total_income += abs(balance)
    
    # Expense accounts
    expense_accounts = Account.query.filter_by(account_type='expense', is_active=True).all()
    expense_data = []
    total_expenses = 0
    
    for account in expense_accounts:
        balance = account.get_balance(end_date) - account.get_balance(start_date)
        if balance != 0:
            expense_data.append({'account': account, 'amount': abs(balance)})
            total_expenses += abs(balance)
    
    net_income = total_income - total_expenses
    
    return render_template('finance/income_statement.html',
        income_data=income_data,
        expense_data=expense_data,
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=net_income,
        start_date=start_date,
        end_date=end_date
    )


@finance_bp.route('/reports/balance-sheet')
@login_required
@require_finance_role
def balance_sheet():
    """Generate balance sheet"""
    as_of_date = request.args.get('as_of_date')
    if as_of_date:
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
    else:
        as_of_date = date.today()
    
    # Assets
    asset_accounts = Account.query.filter_by(account_type='asset', is_active=True).order_by(Account.code).all()
    assets = []
    total_assets = 0
    
    for account in asset_accounts:
        balance = account.get_balance(as_of_date)
        if balance != 0:
            assets.append({'account': account, 'balance': balance})
            total_assets += balance
    
    # Liabilities
    liability_accounts = Account.query.filter_by(account_type='liability', is_active=True).order_by(Account.code).all()
    liabilities = []
    total_liabilities = 0
    
    for account in liability_accounts:
        balance = account.get_balance(as_of_date)
        if balance != 0:
            liabilities.append({'account': account, 'balance': balance})
            total_liabilities += balance
    
    # Equity
    equity_accounts = Account.query.filter_by(account_type='equity', is_active=True).order_by(Account.code).all()
    equity = []
    total_equity = 0
    
    for account in equity_accounts:
        balance = account.get_balance(as_of_date)
        if balance != 0:
            equity.append({'account': account, 'balance': balance})
            total_equity += balance
    
    # Calculate retained earnings (income - expenses)
    income_accounts = Account.query.filter_by(account_type='income', is_active=True).all()
    expense_accounts = Account.query.filter_by(account_type='expense', is_active=True).all()
    
    total_income = sum(account.get_balance(as_of_date) for account in income_accounts)
    total_expenses = sum(account.get_balance(as_of_date) for account in expense_accounts)
    retained_earnings = total_income - total_expenses
    
    total_equity += retained_earnings
    
    return render_template('finance/balance_sheet.html',
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        retained_earnings=retained_earnings,
        as_of_date=as_of_date
    )


@finance_bp.route('/reports/cash-flow')
@login_required
@require_finance_role
def cash_flow_statement():
    """Generate cash flow statement"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = date.today().replace(day=1)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()
    
    # Get cash account movements
    cash_accounts = Account.query.filter(
        Account.account_type == 'asset',
        Account.code.like('1%')  # Typically cash accounts start with 1
    ).all()
    
    # Operating activities - receipts
    receipts = Payment.query.filter(
        Payment.status == 'completed',
        Payment.completed_at >= datetime.combine(start_date, datetime.min.time()),
        Payment.completed_at <= datetime.combine(end_date, datetime.max.time())
    ).all()
    
    total_receipts = sum(p.amount for p in receipts)
    
    # Operating activities - payments
    payments = Voucher.query.filter(
        Voucher.status == 'paid',
        Voucher.voucher_type == 'payment',
        Voucher.paid_at >= datetime.combine(start_date, datetime.min.time()),
        Voucher.paid_at <= datetime.combine(end_date, datetime.max.time())
    ).all()
    
    total_payments = sum(v.amount for v in payments)
    
    net_cash_flow = total_receipts - total_payments
    
    # Opening and closing balances
    opening_balance = sum(acc.get_balance(start_date - timedelta(days=1)) for acc in cash_accounts)
    closing_balance = opening_balance + net_cash_flow
    
    return render_template('finance/cash_flow.html',
        receipts=receipts,
        payments=payments,
        total_receipts=total_receipts,
        total_payments=total_payments,
        net_cash_flow=net_cash_flow,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        start_date=start_date,
        end_date=end_date
    )


# ==================== BUDGET ====================

@finance_bp.route('/budget')
@login_required
@require_finance_role
def budget_overview():
    """Budget overview and tracking"""
    budget_lines = BudgetLine.query.all()
    periods = FinancialPeriod.query.order_by(FinancialPeriod.start_date.desc()).all()
    
    # Calculate totals
    total_budget = sum(b.budgeted_amount or 0 for b in budget_lines)
    total_actual = sum(b.actual_amount or 0 for b in budget_lines)
    variance = total_budget - total_actual
    utilization = (total_actual / total_budget * 100) if total_budget > 0 else 0
    
    return render_template('finance/budget.html',
        budget_lines=budget_lines,
        periods=periods,
        selected_period=None,
        total_budget=total_budget,
        total_actual=total_actual,
        variance=variance,
        utilization=utilization
    )


@finance_bp.route('/budget/create', methods=['GET', 'POST'])
@login_required
@require_finance_role
def create_budget_line():
    """Create a budget line item"""
    if request.method == 'POST':
        budget = BudgetLine(
            category=request.form.get('category'),
            description=request.form.get('description'),
            budgeted_amount=float(request.form.get('budgeted_amount', 0)),
            account_id=request.form.get('account_id') or None
        )
        db.session.add(budget)
        db.session.commit()
        
        flash('Budget line created successfully.', 'success')
        return redirect(url_for('finance.budget_overview'))
    
    accounts = Account.query.filter_by(account_type='expense', is_active=True).all()
    return render_template('finance/create_budget.html', accounts=accounts)


# ==================== EXPORT ====================

@finance_bp.route('/export/vouchers')
@login_required
@require_finance_role
def export_vouchers():
    """Export vouchers to CSV"""
    vouchers = Voucher.query.order_by(Voucher.date.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Voucher No', 'Type', 'Date', 'Payee', 'Amount', 'Payment Method', 'Status', 'Narration'])
    
    for v in vouchers:
        writer.writerow([
            v.voucher_number, v.voucher_type, v.date.strftime('%Y-%m-%d'),
            v.payee_name, v.amount, v.payment_method, v.status, v.narration
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=vouchers_{date.today()}.csv'}
    )


@finance_bp.route('/export/journals')
@login_required
@require_finance_role
def export_journals():
    """Export journal entries to CSV"""
    entries = JournalEntry.query.filter_by(status='posted').order_by(JournalEntry.date.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Entry No', 'Date', 'Account Code', 'Account Name', 'Description', 'Debit', 'Credit'])
    
    for entry in entries:
        for line in entry.lines:
            writer.writerow([
                entry.entry_number, entry.date.strftime('%Y-%m-%d'),
                line.account.code, line.account.name, line.description or entry.description,
                line.debit, line.credit
            ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=journals_{date.today()}.csv'}
    )


@finance_bp.route('/export/accounts')
@login_required
@require_finance_role
def export_accounts():
    """Export chart of accounts to CSV"""
    accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Code', 'Account Name', 'Type', 'Normal Balance', 'Current Balance', 'Description'])
    
    for account in accounts:
        writer.writerow([
            account.code, account.name, account.account_type,
            account.normal_balance, account.current_balance, account.description or ''
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=chart_of_accounts_{date.today()}.csv'}
    )


# ==================== PAYMENT APPROVALS ====================

@finance_bp.route('/payment-approvals')
@login_required
@require_finance_role
def payment_approvals():
    """List payments pending finance approval"""
    from app.models.user import User
    
    # Get pending payments
    pending_payments = Payment.query.filter(
        Payment.finance_status == 'pending_approval'
    ).order_by(Payment.created_at.desc()).all()
    
    # Calculate totals
    total_pending = sum(p.amount for p in pending_payments)
    
    return render_template('finance/payment_approvals.html',
                         pending_payments=pending_payments,
                         total_pending=total_pending)


@finance_bp.route('/payment/<int:payment_id>/approve', methods=['POST'])
@login_required
@require_finance_role
def approve_payment(payment_id):
    """Approve a payment submitted by chair"""
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.finance_status != 'pending_approval':
        flash('This payment is not pending approval.', 'warning')
        return redirect(url_for('finance.payment_approvals'))
    
    notes = request.form.get('notes', '')
    
    try:
        # Approve the payment
        payment.approve_by_finance(current_user.id, notes)
        
        # Mark all associated delegates as paid and issue tickets
        tickets_issued = 0
        for delegate in payment.delegates:
            delegate.is_paid = True
            delegate.payment_confirmed_by = current_user.id
            delegate.payment_confirmed_at = datetime.utcnow()
            if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                from app.models.event import Event
                event = Event.query.get(delegate.event_id) if delegate.event_id else None
                delegate.ticket_number = Delegate.generate_ticket_number(event)
                tickets_issued += 1
        
        db.session.commit()
        
        delegate_count = payment.delegates.count()
        flash(f'Payment of KES {payment.amount:,.2f} approved successfully. {delegate_count} delegate(s) marked as paid. {tickets_issued} ticket(s) issued.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error approving payment: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error approving payment: {str(e)}', 'danger')
    
    return redirect(url_for('finance.payment_approvals'))


@finance_bp.route('/payments/bulk-approve', methods=['POST'])
@login_required
@require_finance_role
def bulk_approve_payments():
    """Bulk approve multiple payments submitted by chairs"""
    payment_ids_str = request.form.get('payment_ids', '')
    notes = request.form.get('notes', '')
    
    if not payment_ids_str:
        flash('No payments selected for approval.', 'warning')
        return redirect(url_for('finance.payment_approvals'))
    
    try:
        payment_ids = [int(pid.strip()) for pid in payment_ids_str.split(',') if pid.strip()]
    except ValueError:
        flash('Invalid payment IDs provided.', 'danger')
        return redirect(url_for('finance.payment_approvals'))
    
    if not payment_ids:
        flash('No valid payments selected for approval.', 'warning')
        return redirect(url_for('finance.payment_approvals'))
    
    approved_count = 0
    total_amount = 0
    total_delegates = 0
    tickets_issued = 0
    errors = []
    
    try:
        for payment_id in payment_ids:
            payment = Payment.query.get(payment_id)
            if not payment:
                errors.append(f'Payment {payment_id} not found')
                continue
                
            if payment.finance_status != 'pending_approval':
                errors.append(f'Payment {payment_id} is not pending approval')
                continue
            
            try:
                # Approve the payment
                payment.approve_by_finance(current_user.id, notes)
                
                # Mark all associated delegates as paid and issue tickets
                for delegate in payment.delegates:
                    delegate.is_paid = True
                    delegate.payment_confirmed_by = current_user.id
                    delegate.payment_confirmed_at = datetime.utcnow()
                    if not delegate.ticket_number or delegate.ticket_number.startswith('PENDING-'):
                        from app.models.event import Event
                        event = Event.query.get(delegate.event_id) if delegate.event_id else None
                        delegate.ticket_number = Delegate.generate_ticket_number(event)
                        tickets_issued += 1
                    total_delegates += 1
                
                approved_count += 1
                total_amount += payment.amount
                
            except Exception as e:
                errors.append(f'Error approving payment {payment_id}: {str(e)}')
                continue
        
        db.session.commit()
        
        if approved_count > 0:
            flash(f'Successfully approved {approved_count} payment(s) totaling KES {total_amount:,.2f}. '
                  f'{total_delegates} delegate(s) marked as paid. {tickets_issued} ticket(s) issued.', 'success')
        
        if errors:
            for error in errors:
                flash(error, 'warning')
                
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error in bulk approve: {str(e)}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error processing bulk approval: {str(e)}', 'danger')
    
    return redirect(url_for('finance.payment_approvals'))


@finance_bp.route('/payment/<int:payment_id>/reject', methods=['POST'])
@login_required
@require_finance_role
def reject_payment(payment_id):
    """Reject a payment submitted by chair"""
    payment = Payment.query.get_or_404(payment_id)
    
    if payment.finance_status != 'pending_approval':
        flash('This payment is not pending approval.', 'warning')
        return redirect(url_for('finance.payment_approvals'))
    
    reason = request.form.get('reason', 'No reason provided')
    
    try:
        # Reject the payment
        payment.reject_by_finance(current_user.id, reason)
        
        # Unlink delegates from this payment (they remain unpaid)
        for delegate in payment.delegates:
            delegate.payment_id = None
        
        db.session.commit()
        
        flash(f'Payment of KES {payment.amount:,.2f} rejected. Chair has been notified.', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error rejecting payment: {str(e)}', 'danger')
    
    return redirect(url_for('finance.payment_approvals'))


@finance_bp.route('/payment/<int:payment_id>/details')
@login_required
@require_finance_role
def payment_details(payment_id):
    """View payment details for approval"""
    from app.models.user import User
    
    payment = Payment.query.get_or_404(payment_id)
    
    # Get chair info
    chair = User.query.get(payment.confirmed_by_chair_id) if payment.confirmed_by_chair_id else None
    
    return render_template('finance/payment_details.html',
                         payment=payment,
                         chair=chair)


@finance_bp.route('/approved-payments')
@login_required
@require_finance_role
def approved_payments():
    """List approved payments"""
    # Get filter parameters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Payment.query.filter(Payment.finance_status == 'approved')
    
    if date_from:
        query = query.filter(Payment.approved_by_finance_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Payment.approved_by_finance_at <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    
    payments = query.order_by(Payment.approved_by_finance_at.desc()).all()
    total_approved = sum(p.amount for p in payments)
    
    return render_template('finance/approved_payments.html',
                         payments=payments,
                         total_approved=total_approved)


@finance_bp.route('/rejected-payments')
@login_required
@require_finance_role
def rejected_payments():
    """List rejected payments"""
    payments = Payment.query.filter(
        Payment.finance_status == 'rejected'
    ).order_by(Payment.created_at.desc()).all()
    
    return render_template('finance/rejected_payments.html',
                         payments=payments)


# ==================== INITIALIZE DEFAULT ACCOUNTS ====================

@finance_bp.route('/setup/initialize', methods=['POST'])
@login_required
@require_finance_role
def initialize_accounts():
    """Initialize default chart of accounts"""
    if AccountCategory.query.count() > 0:
        flash('Accounts already initialized.', 'info')
        return redirect(url_for('finance.chart_of_accounts'))
    
    # Create default categories
    categories_data = [
        {'code': '1000', 'name': 'Current Assets', 'type': 'asset'},
        {'code': '1500', 'name': 'Fixed Assets', 'type': 'asset'},
        {'code': '2000', 'name': 'Current Liabilities', 'type': 'liability'},
        {'code': '2500', 'name': 'Long-term Liabilities', 'type': 'liability'},
        {'code': '3000', 'name': 'Equity', 'type': 'equity'},
        {'code': '4000', 'name': 'Income', 'type': 'income'},
        {'code': '5000', 'name': 'Expenses', 'type': 'expense'},
    ]
    
    for cat_data in categories_data:
        category = AccountCategory(**cat_data)
        db.session.add(category)
    
    db.session.flush()
    
    # Create default accounts
    accounts_data = [
        # Assets
        {'code': '1001', 'name': 'Cash on Hand', 'account_type': 'asset', 'normal_balance': 'debit', 'is_system': True},
        {'code': '1002', 'name': 'M-Pesa Account', 'account_type': 'asset', 'normal_balance': 'debit', 'is_system': True},
        {'code': '1003', 'name': 'Bank Account', 'account_type': 'asset', 'normal_balance': 'debit'},
        {'code': '1010', 'name': 'Accounts Receivable', 'account_type': 'asset', 'normal_balance': 'debit'},
        {'code': '1020', 'name': 'Prepaid Expenses', 'account_type': 'asset', 'normal_balance': 'debit'},
        
        # Liabilities
        {'code': '2001', 'name': 'Accounts Payable', 'account_type': 'liability', 'normal_balance': 'credit'},
        {'code': '2010', 'name': 'Accrued Expenses', 'account_type': 'liability', 'normal_balance': 'credit'},
        {'code': '2020', 'name': 'Deposits Received', 'account_type': 'liability', 'normal_balance': 'credit'},
        
        # Equity
        {'code': '3001', 'name': 'Opening Balance Equity', 'account_type': 'equity', 'normal_balance': 'credit'},
        {'code': '3010', 'name': 'Retained Earnings', 'account_type': 'equity', 'normal_balance': 'credit'},
        
        # Income
        {'code': '4001', 'name': 'Delegate Registration Fees', 'account_type': 'income', 'normal_balance': 'credit', 'is_system': True},
        {'code': '4010', 'name': 'Donations', 'account_type': 'income', 'normal_balance': 'credit'},
        {'code': '4020', 'name': 'Sponsorships', 'account_type': 'income', 'normal_balance': 'credit'},
        {'code': '4030', 'name': 'Offerings', 'account_type': 'income', 'normal_balance': 'credit'},
        {'code': '4040', 'name': 'Merchandise Sales', 'account_type': 'income', 'normal_balance': 'credit'},
        {'code': '4090', 'name': 'Other Income', 'account_type': 'income', 'normal_balance': 'credit'},
        
        # Expenses
        {'code': '5001', 'name': 'Venue & Accommodation', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5010', 'name': 'Catering & Meals', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5020', 'name': 'Transport', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5030', 'name': 'Printing & Stationery', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5040', 'name': 'Communication', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5050', 'name': 'Equipment & Supplies', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5060', 'name': 'Honoraria & Allowances', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5070', 'name': 'Entertainment', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5080', 'name': 'Decorations', 'account_type': 'expense', 'normal_balance': 'debit'},
        {'code': '5090', 'name': 'Miscellaneous Expenses', 'account_type': 'expense', 'normal_balance': 'debit'},
    ]
    
    categories = {c.type: c for c in AccountCategory.query.all()}
    
    for acc_data in accounts_data:
        acc_type = acc_data['account_type']
        if acc_type in categories:
            acc_data['category_id'] = categories[acc_type].id
        account = Account(**acc_data)
        db.session.add(account)
    
    db.session.commit()
    
    flash('Chart of accounts initialized successfully.', 'success')
    return redirect(url_for('finance.chart_of_accounts'))
