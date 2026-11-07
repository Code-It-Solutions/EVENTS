"""Debug script to check pending delegates and chair matching"""
from app import create_app, db
from app.models.pending_delegate import PendingDelegate
from app.models.user import User

app = create_app()
with app.app_context():
    # Check pending delegates
    pending = PendingDelegate.query.all()
    print('=== PENDING DELEGATES ===')
    for p in pending:
        print(f'  {p.name}')
        print(f'    Church: "{p.local_church}"')
        print(f'    Parish: "{p.parish}"') 
        print(f'    Arch: "{p.archdeaconry}"')
        print(f'    Status: {p.status}')
    if not pending:
        print('  (none found)')
    
    # Check chair users
    print()
    print('=== CHAIR USERS ===')
    chairs = User.query.filter_by(role='chair').all()
    for c in chairs:
        print(f'  {c.name}')
        print(f'    Church: "{c.local_church}"')
        print(f'    Parish: "{c.parish}"')
        print(f'    Arch: "{c.archdeaconry}"')
    if not chairs:
        print('  (none found)')
    
    # Check admins
    print()
    print('=== ADMIN USERS ===')
    admins = User.query.filter(User.role.in_(['admin', 'super_admin'])).all()
    for a in admins:
        print(f'  {a.name} ({a.role})')
    if not admins:
        print('  (none found)')
