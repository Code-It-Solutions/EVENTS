"""
Script to add Chair and Archdeaconry Chair roles to the database.
Run this once after updating the code:
    python add_new_roles.py
"""

from app import create_app, db
from app.models.audit import Role

app = create_app()


def add_new_roles():
    with app.app_context():
        # New roles to add
        new_roles = [
            {
                'name': 'chair',
                'description': 'Parish Chair - can register delegates from their parish',
                'permissions': [
                    'delegates.view', 'delegates.create', 'delegates.edit',
                    'payments.view', 'payments.process',
                    'check_in.view',
                    'funds.view', 'funds.create', 'funds.transfer'
                ],
                'is_system': True
            },
            {
                'name': 'archdeaconry_chair',
                'description': 'Archdeaconry Chair - can register intercessors and counsellors for their archdeaconry',
                'permissions': [
                    'delegates.view', 'delegates.create', 'delegates.edit',
                    'intercessors.create', 'intercessors.view', 'intercessors.edit',
                    'counsellors.create', 'counsellors.view', 'counsellors.edit',
                    'payments.view', 'payments.process',
                    'check_in.view',
                    'reports.view',
                    'funds.view', 'funds.create', 'funds.approve', 'funds.transfer'
                ],
                'is_system': True
            },
            {
                'name': 'finance',
                'description': 'Finance Officer - manages fund confirmations and approvals',
                'permissions': [
                    'payments.view', 'payments.process', 'payments.approve',
                    'reports.view', 'reports.export',
                    'funds.view', 'funds.approve', 'funds.complete', 'funds.reports'
                ],
                'is_system': True
            }
        ]
        
        for role_data in new_roles:
            existing = Role.query.filter_by(name=role_data['name']).first()
            if not existing:
                role = Role(
                    name=role_data['name'],
                    description=role_data['description'],
                    is_system=role_data['is_system']
                )
                role.set_permissions(role_data['permissions'])
                db.session.add(role)
                print(f"✓ Added role: {role_data['name']}")
            else:
                print(f"ℹ Role already exists: {role_data['name']}")
        
        db.session.commit()
        print("\n✓ Done! All roles are now available.")
        
        # List all roles
        print("\nCurrent roles:")
        for role in Role.query.order_by(Role.name).all():
            print(f"  - {role.name}: {role.description}")


if __name__ == '__main__':
    add_new_roles()
