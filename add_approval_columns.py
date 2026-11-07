"""Add admin approval fields to users table

This migration adds fields for admin approval workflow:
- is_approved: Boolean flag for approval status
- approval_status: pending/approved/rejected
- approved_by: Admin who approved/rejected
- approved_at: Timestamp of approval/rejection
- rejection_reason: Reason for rejection
"""

from app import create_app, db
from sqlalchemy import text

def upgrade():
    app = create_app()
    with app.app_context():
        # Check if columns already exist
        result = db.session.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'is_approved' not in columns:
            print("Adding is_approved column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT 0"))
        
        if 'approval_status' not in columns:
            print("Adding approval_status column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending'"))
        
        if 'approved_by' not in columns:
            print("Adding approved_by column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN approved_by INTEGER"))
        
        if 'approved_at' not in columns:
            print("Adding approved_at column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN approved_at DATETIME"))
        
        if 'rejection_reason' not in columns:
            print("Adding rejection_reason column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN rejection_reason VARCHAR(500)"))
        
        # Set existing admin users as approved
        print("Setting existing admin users as approved...")
        db.session.execute(text("""
            UPDATE users 
            SET is_approved = 1, approval_status = 'approved' 
            WHERE role IN ('admin', 'super_admin')
        """))
        
        # Set existing active chairs as approved (grandfathering existing users)
        print("Approving existing active chair users...")
        db.session.execute(text("""
            UPDATE users 
            SET is_approved = 1, approval_status = 'approved' 
            WHERE role = 'chair' AND is_active = 1 AND is_approved IS NULL
        """))
        
        db.session.commit()
        print("Migration completed successfully!")

if __name__ == '__main__':
    upgrade()
