"""
Script to initialize the database and create an admin user.
Run this after setting up your environment:
    python init_db.py
"""

from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Event, PricingTier, Role

app = create_app()


def init_database():
    with app.app_context():
        # Create all tables
        try:
            db.create_all()
            print("✓ Database tables created successfully!")
        except Exception as e:
            print(f"⚠ Table creation warning: {e}")
            print("  Continuing with existing tables...")
        
        # Create default roles
        try:
            Role.create_default_roles()
            print("✓ Default roles created!")
        except Exception as e:
            print(f"ℹ Roles may already exist: {e}")
        
        # Check if admin exists
        admin = User.query.filter_by(email='admin@kayo.org').first()
        
        if not admin:
            # Get super_admin role
            super_admin_role = Role.query.filter_by(name='super_admin').first()
            
            # Create default admin user
            admin = User(
                name='Admin',
                email='admin@kayo.org',
                role='super_admin',
                role_id=super_admin_role.id if super_admin_role else None,
                is_active=True
            )
            admin.set_password('admin123')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created!")
            print("  Email: admin@kayo.org")
            print("  Password: admin123")
            print("  ⚠️  Please change this password immediately!")
        else:
            print("ℹ Admin user already exists.")
        
        # Create default event if none exists
        event = Event.query.first()
        if not event:
            event = Event(
                name='KAYO Annual Conference 2025',
                slug='kayo',
                description='Kenya Anglican Youth Organization Annual Conference',
                start_date=datetime.utcnow().date() + timedelta(days=30),
                end_date=datetime.utcnow().date() + timedelta(days=33),
                registration_deadline=datetime.utcnow() + timedelta(days=25),
                venue='ACK Guest House, Nairobi',
                is_active=True,
                is_published=True,
                created_by=admin.id
            )
            db.session.add(event)
            db.session.commit()
            print("✓ Default event created!")
            
            # Create pricing tiers
            tiers = [
                PricingTier(
                    event_id=event.id,
                    name='Early Bird',
                    description='Register early and save!',
                    price=2500,
                    valid_until=datetime.utcnow() + timedelta(days=14),
                    is_active=True
                ),
                PricingTier(
                    event_id=event.id,
                    name='Regular',
                    description='Standard registration fee',
                    price=3000,
                    valid_from=datetime.utcnow() + timedelta(days=14),
                    is_active=True
                ),
                PricingTier(
                    event_id=event.id,
                    name='VIP',
                    description='VIP package with premium benefits',
                    price=5000,
                    is_active=True
                ),
                PricingTier(
                    event_id=event.id,
                    name='Group (10+)',
                    description='Group discount for 10 or more delegates',
                    price=2500,
                    group_min_size=10,
                    group_discount_percent=10,
                    is_active=True
                )
            ]
            for tier in tiers:
                db.session.add(tier)
            db.session.commit()
            print("✓ Pricing tiers created!")
            
            # Update admin's current event
            admin.current_event_id = event.id
            db.session.commit()
        else:
            print("ℹ Event already exists.")
        
        print("\n✓ Database initialization complete!")


if __name__ == '__main__':
    init_database()
