"""
Script to fix missing database schema elements.
This adds:
1. session_token column to users table
2. fund management tables (pledges, scheduled_payments, fund_transfers, etc.)

Run this once to fix the database:
    python fix_database_schema.py
"""

from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns


def table_exists(table_name):
    """Check if a table exists"""
    with app.app_context():
        inspector = inspect(db.engine)
        return table_name in inspector.get_table_names()


def add_session_token_column():
    """Add session_token column to users table"""
    with app.app_context():
        try:
            if not column_exists('users', 'session_token'):
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN session_token VARCHAR(64)"
                ))
                db.session.commit()
                print("✓ Added session_token column to users table")
            else:
                print("ℹ session_token column already exists")
        except Exception as e:
            print(f"Error adding session_token: {e}")
            db.session.rollback()


def create_pledges_table():
    """Create pledges table if it doesn't exist"""
    with app.app_context():
        if table_exists('pledges'):
            print("ℹ pledges table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE pledges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type VARCHAR(50) NOT NULL,
                    source_name VARCHAR(100) NOT NULL,
                    source_phone VARCHAR(15),
                    source_email VARCHAR(120),
                    delegate_id INTEGER REFERENCES delegates(id),
                    amount_pledged FLOAT NOT NULL,
                    amount_paid FLOAT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'pending',
                    event_id INTEGER REFERENCES events(id),
                    recorded_by INTEGER NOT NULL REFERENCES users(id),
                    local_church VARCHAR(100),
                    parish VARCHAR(100),
                    archdeaconry VARCHAR(100),
                    description TEXT,
                    due_date DATE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            print("✓ Created pledges table")
        except Exception as e:
            print(f"Error creating pledges table: {e}")
            db.session.rollback()


def create_pledge_payments_table():
    """Create pledge_payments table if it doesn't exist"""
    with app.app_context():
        if table_exists('pledge_payments'):
            print("ℹ pledge_payments table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE pledge_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pledge_id INTEGER NOT NULL REFERENCES pledges(id),
                    amount FLOAT NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    reference VARCHAR(100),
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    confirmed_by INTEGER REFERENCES users(id),
                    confirmed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            print("✓ Created pledge_payments table")
        except Exception as e:
            print(f"Error creating pledge_payments table: {e}")
            db.session.rollback()


def create_scheduled_payments_table():
    """Create scheduled_payments table if it doesn't exist"""
    with app.app_context():
        if table_exists('scheduled_payments'):
            print("ℹ scheduled_payments table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE scheduled_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type VARCHAR(50) NOT NULL,
                    source_name VARCHAR(100) NOT NULL,
                    source_phone VARCHAR(15),
                    source_email VARCHAR(120),
                    delegate_id INTEGER REFERENCES delegates(id),
                    amount FLOAT NOT NULL,
                    frequency VARCHAR(20) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    next_payment_date DATE,
                    total_expected FLOAT DEFAULT 0,
                    total_collected FLOAT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active',
                    event_id INTEGER REFERENCES events(id),
                    recorded_by INTEGER NOT NULL REFERENCES users(id),
                    local_church VARCHAR(100),
                    parish VARCHAR(100),
                    archdeaconry VARCHAR(100),
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            print("✓ Created scheduled_payments table")
        except Exception as e:
            print(f"Error creating scheduled_payments table: {e}")
            db.session.rollback()


def create_scheduled_payment_installments_table():
    """Create scheduled_payment_installments table if it doesn't exist"""
    with app.app_context():
        if table_exists('scheduled_payment_installments'):
            print("ℹ scheduled_payment_installments table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE scheduled_payment_installments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheduled_payment_id INTEGER NOT NULL REFERENCES scheduled_payments(id),
                    due_date DATE NOT NULL,
                    amount_due FLOAT NOT NULL,
                    amount_paid FLOAT DEFAULT 0,
                    payment_method VARCHAR(50),
                    reference VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending',
                    confirmed_by INTEGER REFERENCES users(id),
                    confirmed_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME
                )
            """))
            db.session.commit()
            print("✓ Created scheduled_payment_installments table")
        except Exception as e:
            print(f"Error creating scheduled_payment_installments table: {e}")
            db.session.rollback()


def create_fund_transfers_table():
    """Create fund_transfers table if it doesn't exist"""
    with app.app_context():
        if table_exists('fund_transfers'):
            print("ℹ fund_transfers table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE fund_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_number VARCHAR(50) NOT NULL UNIQUE,
                    amount FLOAT NOT NULL,
                    from_user_id INTEGER NOT NULL REFERENCES users(id),
                    from_role VARCHAR(50) NOT NULL,
                    to_user_id INTEGER NOT NULL REFERENCES users(id),
                    to_role VARCHAR(50) NOT NULL,
                    transfer_stage VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    local_church VARCHAR(100),
                    parish VARCHAR(100),
                    archdeaconry VARCHAR(100),
                    event_id INTEGER REFERENCES events(id),
                    description TEXT,
                    attachments TEXT DEFAULT '[]',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    submitted_at DATETIME,
                    approved_at DATETIME,
                    completed_at DATETIME
                )
            """))
            db.session.commit()
            print("✓ Created fund_transfers table")
        except Exception as e:
            print(f"Error creating fund_transfers table: {e}")
            db.session.rollback()


def create_fund_transfer_approvals_table():
    """Create fund_transfer_approvals table if it doesn't exist"""
    with app.app_context():
        if table_exists('fund_transfer_approvals'):
            print("ℹ fund_transfer_approvals table already exists")
            return
        
        try:
            db.session.execute(text("""
                CREATE TABLE fund_transfer_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transfer_id INTEGER NOT NULL REFERENCES fund_transfers(id),
                    approved_by INTEGER NOT NULL REFERENCES users(id),
                    action VARCHAR(20) NOT NULL,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()
            print("✓ Created fund_transfer_approvals table")
        except Exception as e:
            print(f"Error creating fund_transfer_approvals table: {e}")
            db.session.rollback()


def fix_database():
    """Run all database fixes"""
    print("\n=== Fixing Database Schema ===\n")
    
    # Add missing column
    add_session_token_column()
    
    # Create missing tables
    create_pledges_table()
    create_pledge_payments_table()
    create_scheduled_payments_table()
    create_scheduled_payment_installments_table()
    create_fund_transfers_table()
    create_fund_transfer_approvals_table()
    
    print("\n=== Database Schema Fix Complete ===\n")


if __name__ == '__main__':
    fix_database()
