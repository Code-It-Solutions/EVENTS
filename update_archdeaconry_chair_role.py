"""
Script to update the archdeaconry_chair role permissions.
Archdeaconry Chairs can register Intercessors and Counsellors for their archdeaconry.
Run this after applying the code changes to update existing role permissions.
"""
from app import create_app, db
from app.models.audit import Role


def update_archdeaconry_chair_role():
    """Update archdeaconry_chair role with proper permissions"""
    app = create_app()
    
    with app.app_context():
        print("Updating Archdeaconry Chair role...")
        
        # Find the archdeaconry_chair role
        role = Role.query.filter_by(name='archdeaconry_chair').first()
        
        new_permissions = [
            'delegates.view', 'delegates.create', 'delegates.edit',
            'intercessors.create', 'intercessors.view', 'intercessors.edit',
            'counsellors.create', 'counsellors.view', 'counsellors.edit',
            'payments.view', 'payments.process',
            'check_in.view',
            'reports.view',
            'funds.view', 'funds.create', 'funds.approve', 'funds.transfer'
        ]
        
        if role:
            # Update permissions
            role.set_permissions(new_permissions)
            role.description = 'Archdeaconry Chair - can register intercessors and counsellors for their archdeaconry'
            
            db.session.commit()
            print(f"✅ Updated archdeaconry_chair role permissions")
        else:
            print("⚠️ archdeaconry_chair role not found. Creating it...")
            role = Role(
                name='archdeaconry_chair',
                description='Archdeaconry Chair - can register intercessors and counsellors for their archdeaconry',
                is_system=True
            )
            role.set_permissions(new_permissions)
            db.session.add(role)
            db.session.commit()
            print("✅ Created archdeaconry_chair role")
        
        print("\n📋 Archdeaconry Chair permissions:")
        print("   ✓ View/Create/Edit delegates (for their archdeaconry)")
        print("   ✓ Create/View/Edit intercessors")
        print("   ✓ Create/View/Edit counsellors")
        print("   ✓ View and process payments")
        print("   ✓ View check-in status")
        print("   ✓ View reports")
        print("   ✓ Manage funds (view, create, approve, transfer)")
        print()
        print("Note: Archdeaconry Chairs are responsible for:")
        print("   - Registering Intercessors for their archdeaconry")
        print("   - Registering Counsellors for their archdeaconry")
        print("   - NOT registering regular delegates (that's for Parish Chairs)")


if __name__ == '__main__':
    update_archdeaconry_chair_role()
