"""
Fix database schema - add missing tables and columns
"""
from app import create_app, db
from sqlalchemy import text

def fix_schema():
    app = create_app()
    with app.app_context():
        print("Checking and fixing database schema...")
        
        # Check existing columns in delegates table
        result = db.session.execute(text("PRAGMA table_info(delegates)"))
        columns = [row[1] for row in result.fetchall()]
        print(f"Current delegates columns: {columns}")
        
        # Add missing columns to delegates
        if 'payment_confirmed_by' not in columns:
            print("Adding payment_confirmed_by column...")
            db.session.execute(text("ALTER TABLE delegates ADD COLUMN payment_confirmed_by INTEGER REFERENCES users(id)"))
            db.session.commit()
            print("✅ Added payment_confirmed_by")
        
        if 'payment_confirmed_at' not in columns:
            print("Adding payment_confirmed_at column...")
            db.session.execute(text("ALTER TABLE delegates ADD COLUMN payment_confirmed_at DATETIME"))
            db.session.commit()
            print("✅ Added payment_confirmed_at")
        
        # Check existing columns in payments table
        result = db.session.execute(text("PRAGMA table_info(payments)"))
        payment_columns = [row[1] for row in result.fetchall()]
        print(f"Current payments columns: {payment_columns}")
        
        # Add missing columns to payments
        if 'finance_status' not in payment_columns:
            print("Adding finance_status column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN finance_status VARCHAR(50) DEFAULT 'pending'"))
            db.session.commit()
            print("✅ Added finance_status")
        
        if 'confirmed_by_chair_id' not in payment_columns:
            print("Adding confirmed_by_chair_id column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN confirmed_by_chair_id INTEGER REFERENCES users(id)"))
            db.session.commit()
            print("✅ Added confirmed_by_chair_id")
        
        if 'confirmed_by_chair_at' not in payment_columns:
            print("Adding confirmed_by_chair_at column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN confirmed_by_chair_at DATETIME"))
            db.session.commit()
            print("✅ Added confirmed_by_chair_at")
            
        if 'approved_by_finance_id' not in payment_columns:
            print("Adding approved_by_finance_id column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN approved_by_finance_id INTEGER REFERENCES users(id)"))
            db.session.commit()
            print("✅ Added approved_by_finance_id")
            
        if 'approved_by_finance_at' not in payment_columns:
            print("Adding approved_by_finance_at column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN approved_by_finance_at DATETIME"))
            db.session.commit()
            print("✅ Added approved_by_finance_at")
            
        if 'rejection_reason' not in payment_columns:
            print("Adding rejection_reason column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN rejection_reason TEXT"))
            db.session.commit()
            print("✅ Added rejection_reason")
            
        if 'finance_notes' not in payment_columns:
            print("Adding finance_notes column...")
            db.session.execute(text("ALTER TABLE payments ADD COLUMN finance_notes TEXT"))
            db.session.commit()
            print("✅ Added finance_notes")
        
        # Check if user_sessions table exists
        result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'"))
        if not result.fetchone():
            print("Creating user_sessions table...")
            db.session.execute(text("""
                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    session_token VARCHAR(64) NOT NULL UNIQUE,
                    device_info VARCHAR(200),
                    browser VARCHAR(100),
                    os VARCHAR(100),
                    ip_address VARCHAR(50),
                    location VARCHAR(100),
                    created_at DATETIME,
                    last_activity DATETIME,
                    expires_at DATETIME,
                    is_active BOOLEAN DEFAULT 1,
                    is_current BOOLEAN DEFAULT 0
                )
            """))
            db.session.execute(text("CREATE INDEX ix_user_sessions_user_id ON user_sessions(user_id)"))
            db.session.execute(text("CREATE INDEX ix_user_sessions_token ON user_sessions(session_token)"))
            db.session.commit()
            print("✅ Created user_sessions table")
        else:
            print("✅ user_sessions table already exists")
        
        print("\n✅ Database schema fixed!")

if __name__ == '__main__':
    fix_schema()
