from app import create_app, db
from app.models.user import User

app = create_app()
with app.app_context():
    chairs = User.query.filter_by(role='archdeaconry_chair').all()
    print('Archdeaconry Chair Accounts Status:')
    print('-' * 80)
    for u in chairs:
        status = 'ACTIVE' if u.is_active else 'INACTIVE'
        approval = 'APPROVED' if u.is_approved else 'NOT APPROVED'
        print(f'{u.email}: {status}, {approval}')
    
    print(f'\nTotal archdeaconry_chair accounts: {len(chairs)}')
    
    # Count by status
    active_count = sum(1 for u in chairs if u.is_active)
    approved_count = sum(1 for u in chairs if u.is_approved)
    print(f'Active: {active_count}, Approved: {approved_count}')
