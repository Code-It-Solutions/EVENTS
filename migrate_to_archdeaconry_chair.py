"""
Migration script to convert youth_minister role/users to archdeaconry_chair.
This script:
1. Updates existing youth_minister users to archdeaconry_chair role
2. Creates/updates the archdeaconry_chair role with proper permissions
3. Updates any delegates with youth_minister category to archdeaconry_chair

Run this once after deploying the updated code:
    python migrate_to_archdeaconry_chair.py
"""

from app import create_app, db
from app.models.user import User
from app.models.audit import Role
from sqlalchemy import text

app = create_app()


def migrate_to_archdeaconry_chair():
    with app.app_context():
        print("=" * 70)
        print("Migration: Youth Minister → Archdeaconry Chair")
        print("=" * 70)
        print()
        
        # Step 1: Create/Update the archdeaconry_chair role
        print("Step 1: Setting up archdeaconry_chair role...")
        arch_chair_role = Role.query.filter_by(name='archdeaconry_chair').first()
        
        arch_chair_permissions = [
            'delegates.view', 'delegates.create', 'delegates.edit',
            'intercessors.create', 'intercessors.view', 'intercessors.edit',
            'counsellors.create', 'counsellors.view', 'counsellors.edit',
            'payments.view', 'payments.process',
            'check_in.view',
            'reports.view',
            'funds.view', 'funds.create', 'funds.approve', 'funds.transfer'
        ]
        
        if not arch_chair_role:
            arch_chair_role = Role(
                name='archdeaconry_chair',
                description='Archdeaconry Chair - can register intercessors and counsellors for their archdeaconry',
                is_system=True
            )
            arch_chair_role.set_permissions(arch_chair_permissions)
            db.session.add(arch_chair_role)
            print("  ✅ Created archdeaconry_chair role")
        else:
            arch_chair_role.description = 'Archdeaconry Chair - can register intercessors and counsellors for their archdeaconry'
            arch_chair_role.set_permissions(arch_chair_permissions)
            print("  ✅ Updated existing archdeaconry_chair role")
        
        db.session.commit()
        
        # Step 2: Update users with youth_minister role
        print("\nStep 2: Migrating youth_minister users...")
        youth_minister_users = User.query.filter_by(role='youth_minister').all()
        migrated_users = 0
        
        for user in youth_minister_users:
            old_name = user.name
            user.role = 'archdeaconry_chair'
            user.role_id = arch_chair_role.id
            # Update name if it contains "Youth Minister"
            if 'Youth Minister' in user.name:
                user.name = user.name.replace('Youth Minister', 'Chair')
            migrated_users += 1
            print(f"  ✅ {old_name} → {user.name} (role: archdeaconry_chair)")
        
        if migrated_users == 0:
            print("  ℹ No youth_minister users found to migrate")
        
        # Step 3: Update delegates with youth_minister category using raw SQL
        print("\nStep 3: Updating delegate categories...")
        try:
            # Use raw SQL to avoid model column issues
            result = db.session.execute(
                text("UPDATE delegates SET category = 'archdeaconry_chair' WHERE category = 'youth_minister'")
            )
            migrated_delegates = result.rowcount
            if migrated_delegates > 0:
                print(f"  ✅ Updated {migrated_delegates} delegates from youth_minister to archdeaconry_chair")
            else:
                print("  ℹ No delegates with youth_minister category found")
        except Exception as e:
            print(f"  ⚠️ Could not update delegates: {e}")
            migrated_delegates = 0
        
        # Step 4: Optionally remove the old youth_minister role
        print("\nStep 4: Handling old youth_minister role...")
        ym_role = Role.query.filter_by(name='youth_minister').first()
        if ym_role:
            # Check if any users still have this role
            remaining_users = User.query.filter_by(role='youth_minister').count()
            if remaining_users == 0:
                db.session.delete(ym_role)
                print("  ✅ Removed obsolete youth_minister role")
            else:
                print(f"  ⚠️ youth_minister role kept - {remaining_users} users still have this role")
        else:
            print("  ℹ youth_minister role not found")
        
        # Commit all changes
        db.session.commit()
        
        # Summary
        print("\n" + "=" * 70)
        print("Migration Complete!")
        print("=" * 70)
        print(f"  Users migrated: {migrated_users}")
        print(f"  Delegates updated: {migrated_delegates}")
        print()
        print("Note: Archdeaconry Chairs can now register:")
        print("  - Intercessors")
        print("  - Counsellors")
        print()
        print("Parish Chairs register:")
        print("  - Delegates")
        print("=" * 70)


if __name__ == '__main__':
    migrate_to_archdeaconry_chair()
