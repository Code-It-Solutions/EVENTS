"""
Script to update the youth_minister role to have view-only permissions.
Run this after applying the code changes to update existing role permissions.
"""
from app import create_app, db
from app.models.audit import Role

def update_youth_minister_role():
    """Update youth_minister role to have view-only permissions"""
    app = create_app()
    
    with app.app_context():
        print("Updating Youth Minister role to view-only...")
        
        # Find the youth_minister role
        role = Role.query.filter_by(name='youth_minister').first()
        
        if role:
            # Update permissions to view-only
            new_permissions = [
                'delegates.view',
                'payments.view',
                'check_in.view',
                'reports.view'
            ]
            role.set_permissions(new_permissions)
            role.description = 'Youth Minister - view-only access to delegates and reports'
            
            db.session.commit()
            print(f"✅ Updated youth_minister role permissions to: {new_permissions}")
        else:
            print("⚠️ youth_minister role not found. Creating it...")
            role = Role(
                name='youth_minister',
                description='Youth Minister - view-only access to delegates and reports',
                is_system=True
            )
            role.set_permissions([
                'delegates.view',
                'payments.view',
                'check_in.view',
                'reports.view'
            ])
            db.session.add(role)
            db.session.commit()
            print("✅ Created youth_minister role with view-only permissions")
        
        print("\n📋 Youth Minister permissions are now:")
        print("   - View delegates (from their archdeaconry)")
        print("   - View payments")
        print("   - View check-in status")
        print("   - View reports")
        print("\n❌ Youth Ministers can NO longer:")
        print("   - Register new delegates")
        print("   - Edit delegates")
        print("   - Delete delegates")
        print("   - Process payments")

if __name__ == '__main__':
    update_youth_minister_role()
