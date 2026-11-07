"""
Script to create Archdeaconry Chair accounts for all Archdeaconries.
Archdeaconry Chairs can register Intercessors and Counsellors for their archdeaconry.
Email format: archdeaconryname.chair@kayo.com (lowercase, no spaces)
Password format: archdeaconryname123

Run this once:
    python create_archdeaconry_accounts.py
"""

from app import create_app, db
from app.models.user import User
from app.church_data import CHURCH_DATA

app = create_app()


def create_archdeaconry_accounts():
    with app.app_context():
        created_count = 0
        skipped_count = 0
        
        print("=" * 60)
        print("Creating Archdeaconry Chair Accounts for All Archdeaconries")
        print("=" * 60)
        print()
        
        for archdeaconry in CHURCH_DATA.keys():
            # Generate email: remove "Archdeaconry" suffix, lowercase, no spaces
            arch_name_clean = archdeaconry.replace(" Archdeaconry", "").replace("'s", "").replace(".", "")
            arch_name_clean = arch_name_clean.replace(" ", "").replace("-", "").lower()
            
            # Use .chair suffix for archdeaconry chair accounts
            email = f"{arch_name_clean}.chair@kayo.com"
            password = f"{arch_name_clean}123"
            
            # Check if user already exists
            existing = User.query.filter_by(email=email).first()
            if existing:
                print(f"⏭️  {archdeaconry}: Already exists ({email})")
                skipped_count += 1
                continue
            
            # Create new user
            user = User(
                name=f"{archdeaconry} Chair",
                email=email,
                role='archdeaconry_chair',
                archdeaconry=archdeaconry,
                oauth_provider='local',
                is_active=True,
                is_approved=True,
                approval_status='approved'
            )
            user.set_password(password)
            db.session.add(user)
            
            print(f"✅ {archdeaconry}")
            print(f"   Email: {email}")
            print(f"   Password: {password}")
            created_count += 1
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"✅ Created: {created_count} accounts")
        print(f"⏭️  Skipped: {skipped_count} (already existed)")
        print("=" * 60)
        
        # Print summary table
        print("\n📋 ARCHDEACONRY CHAIR ACCOUNT SUMMARY")
        print("=" * 70)
        print(f"{'Archdeaconry':<30} {'Email':<25} {'Password':<15}")
        print("-" * 70)
        
        for archdeaconry in sorted(CHURCH_DATA.keys()):
            arch_name_clean = archdeaconry.replace(" Archdeaconry", "").replace("'s", "").replace(".", "")
            arch_name_clean = arch_name_clean.replace(" ", "").replace("-", "").lower()
            email = f"{arch_name_clean}.chair@kayo.com"
            password = f"{arch_name_clean}123"
            print(f"{archdeaconry:<30} {email:<25} {password:<15}")


if __name__ == '__main__':
    create_archdeaconry_accounts()
