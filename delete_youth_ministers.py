"""Script to delete youth_minister role and users from the database."""
from app import create_app, db
from app.models import User
from app.models.audit import Role

app = create_app()
with app.app_context():
    # Delete users with youth_minister role
    youth_ministers = User.query.filter_by(role='youth_minister').all()
    print(f'Found {len(youth_ministers)} youth minister users')
    if youth_ministers:
        for ym in youth_ministers:
            print(f'  Deleting user: {ym.name} ({ym.email})')
            db.session.delete(ym)
        db.session.commit()
        print(f'Deleted {len(youth_ministers)} youth minister users.')
    
    # Delete youth_minister role from Role table
    ym_role = Role.query.filter_by(name='youth_minister').first()
    if ym_role:
        print(f'\nDeleting youth_minister role (ID: {ym_role.id})')
        db.session.delete(ym_role)
        db.session.commit()
        print('Youth minister role deleted from database.')
    else:
        print('\nNo youth_minister role found in Role table.')
    
    # Show remaining roles
    print('\nRemaining roles:')
    for role in Role.query.all():
        print(f'  - {role.name}')
