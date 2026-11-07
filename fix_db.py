#!/usr/bin/env python
"""Script to create missing tables using raw SQL"""
import os
import sys
import sqlite3

# Find the database file
db_paths = [
    'instance/kayo.db',
    'instance/app.db', 
    'kayo.db',
    'app.db',
    os.path.expanduser('~/KAYO/instance/kayo.db'),
    os.path.expanduser('~/KAYO/instance/app.db'),
]

db_path = None
for path in db_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    # Try to get from config
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from config import Config
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
    except:
        pass

if not db_path:
    print("Could not find database file. Please specify the path.")
    print("Usage: python fix_db.py /path/to/your/database.db")
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        sys.exit(1)

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get existing tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
existing_tables = [row[0] for row in cursor.fetchall()]
print(f"Existing tables: {existing_tables}")

# Add session_token column to users if missing
if 'users' in existing_tables:
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'session_token' not in columns:
        print("Adding session_token column to users...")
        cursor.execute("ALTER TABLE users ADD COLUMN session_token VARCHAR(100)")
        conn.commit()
        print("Added session_token column")

# Create pledges table
if 'pledges' not in existing_tables:
    print("Creating pledges table...")
    cursor.execute('''
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
    ''')
    conn.commit()
    print("Created pledges table")

# Create pledge_payments table
if 'pledge_payments' not in existing_tables:
    print("Creating pledge_payments table...")
    cursor.execute('''
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
    ''')
    conn.commit()
    print("Created pledge_payments table")

# Create scheduled_payments table
if 'scheduled_payments' not in existing_tables:
    print("Creating scheduled_payments table...")
    cursor.execute('''
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
    ''')
    conn.commit()
    print("Created scheduled_payments table")

# Create scheduled_payment_installments table
if 'scheduled_payment_installments' not in existing_tables:
    print("Creating scheduled_payment_installments table...")
    cursor.execute('''
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
    ''')
    conn.commit()
    print("Created scheduled_payment_installments table")

# Create fund_transfers table
if 'fund_transfers' not in existing_tables:
    print("Creating fund_transfers table...")
    cursor.execute('''
        CREATE TABLE fund_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_number VARCHAR(50) UNIQUE NOT NULL,
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
            attachments TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            submitted_at DATETIME,
            approved_at DATETIME,
            completed_at DATETIME
        )
    ''')
    conn.commit()
    print("Created fund_transfers table")

# Verify all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
final_tables = [row[0] for row in cursor.fetchall()]
print(f"\nFinal tables: {final_tables}")

required = ['pledges', 'pledge_payments', 'scheduled_payments', 'scheduled_payment_installments', 'fund_transfers']
for t in required:
    if t in final_tables:
        print(f"SUCCESS: {t}")
    else:
        print(f"MISSING: {t}")

conn.close()
print("\nDone! Remember to reload your web app.")
