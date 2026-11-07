"""
Script to create Youth Chairperson accounts for all parishes.
Email format: parishname@kayo.com (lowercase, no spaces)
Password format: parishname123

Run this once:
    python create_parish_accounts.py
"""

from app import create_app, db
from app.models.user import User
from app.church_data import CHURCH_DATA

app = create_app()


def create_parish_accounts():
    with app.app_context():
        created_count = 0
        skipped_count = 0
        
        print("=" * 60)
        print("Creating Youth Chairperson Accounts for All Parishes")
        print("=" * 60)
        print()
        
        for archdeaconry, parishes in CHURCH_DATA.items():
            print(f"\n📍 {archdeaconry}")
            print("-" * 40)
            
            for parish in parishes:
                # Generate email: remove "Parish" suffix, lowercase, no spaces
                parish_name_clean = parish.replace(" Parish", "").replace("'s", "").replace(".", "")
                parish_name_clean = parish_name_clean.replace(" ", "").replace("-", "").lower()
                
                email = f"{parish_name_clean}@kayo.com"
                password = f"{parish_name_clean}123"
                
                # Check if user already exists
                existing = User.query.filter_by(email=email).first()
                if existing:
                    print(f"  ⏭️  {parish}: Already exists ({email})")
                    skipped_count += 1
                    continue
                
                # Create new user
                user = User(
                    name=f"{parish} Youth Chair",
                    email=email,
                    role='chair',
                    local_church=parish,
                    parish=parish,
                    archdeaconry=archdeaconry,
                    oauth_provider='local',
                    is_active=True
                )
                user.set_password(password)
                db.session.add(user)
                
                print(f"  ✅ {parish}")
                print(f"      Email: {email}")
                print(f"      Password: {password}")
                created_count += 1
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"✅ Created: {created_count} accounts")
        print(f"⏭️  Skipped: {skipped_count} (already existed)")
        print("=" * 60)
        
        # Print summary table
        print("\n📋 ACCOUNT SUMMARY")
        print("=" * 60)
        print(f"{'Parish':<35} {'Email':<25}")
        print("-" * 60)
        
        for archdeaconry, parishes in CHURCH_DATA.items():
            for parish in parishes:
                parish_name_clean = parish.replace(" Parish", "").replace("'s", "").replace(".", "")
                parish_name_clean = parish_name_clean.replace(" ", "").replace("-", "").lower()
                email = f"{parish_name_clean}@kayo.com"
                print(f"{parish:<35} {email:<25}")


if __name__ == '__main__':
    create_parish_accounts()
