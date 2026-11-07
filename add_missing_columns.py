"""
Database migration script to add missing columns.
Run this on PythonAnywhere:
    python add_missing_columns.py
"""

import sqlite3
import os

def add_missing_columns():
    # Find the database file
    db_paths = [
        'instance/kayo.db',
        'kayo.db',
        '/home/Monsiuer/KAYO/instance/kayo.db',
        '/home/Monsiuer/KAYO/kayo.db'
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ Database file not found!")
        print("Looking in paths:", db_paths)
        return
    
    print(f"✓ Found database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of columns to add to delegates table
    delegate_columns = [
        ('payment_confirmed_by', 'INTEGER'),
        ('payment_confirmed_at', 'DATETIME'),
        ('delegate_number', 'INTEGER'),
        ('pricing_tier_id', 'INTEGER'),
        ('custom_field_values', 'TEXT DEFAULT "{}"'),
        ('amount_paid', 'FLOAT DEFAULT 0')
    ]
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(delegates)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    print(f"Existing delegate columns: {existing_columns}")
    
    # Add missing columns to delegates
    for col_name, col_type in delegate_columns:
        if col_name not in existing_columns:
            try:
                sql = f"ALTER TABLE delegates ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"✓ Added column: delegates.{col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"ℹ Column already exists: delegates.{col_name}")
                else:
                    print(f"⚠ Error adding {col_name}: {e}")
        else:
            print(f"ℹ Column already exists: delegates.{col_name}")
    
    # Check and add columns to users table
    cursor.execute("PRAGMA table_info(users)")
    existing_user_columns = [col[1] for col in cursor.fetchall()]
    
    user_columns = [
        ('role_id', 'INTEGER'),
        ('current_event_id', 'INTEGER'),
        ('google_id', 'VARCHAR(100)'),
        ('profile_picture', 'VARCHAR(500)'),
        ('oauth_provider', 'VARCHAR(20)')
    ]
    
    for col_name, col_type in user_columns:
        if col_name not in existing_user_columns:
            try:
                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"✓ Added column: users.{col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"ℹ Column already exists: users.{col_name}")
                else:
                    print(f"⚠ Error adding {col_name}: {e}")
        else:
            print(f"ℹ Column already exists: users.{col_name}")
    
    # Check if roles table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'")
    if not cursor.fetchone():
        print("Creating roles table...")
        cursor.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description VARCHAR(200),
                permissions TEXT DEFAULT '[]',
                is_system BOOLEAN DEFAULT 0,
                created_at DATETIME
            )
        """)
        print("✓ Created roles table")
        
        # Insert default roles
        from datetime import datetime
        import json
        now = datetime.utcnow().isoformat()
        
        default_roles = [
            ('super_admin', 'Full system access', json.dumps(['*']), 1, now),
            ('admin', 'Event administration', json.dumps(['delegates.*', 'payments.*', 'reports.*']), 1, now),
            ('chair', 'Parish chairperson', json.dumps(['delegates.create', 'delegates.view']), 1, now),
            ('archdeaconry_chair', 'Archdeaconry chair - registers intercessors and counsellors', json.dumps(['delegates.create', 'delegates.view', 'intercessors.create', 'intercessors.view', 'counsellors.create', 'counsellors.view']), 1, now),
        ]
        
        cursor.executemany(
            "INSERT OR IGNORE INTO roles (name, description, permissions, is_system, created_at) VALUES (?, ?, ?, ?, ?)",
            default_roles
        )
        print("✓ Added default roles")
    else:
        print("ℹ Roles table already exists")
    
    # Check if events table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if not cursor.fetchone():
        print("Creating events table...")
        cursor.execute("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                registration_deadline DATETIME,
                venue VARCHAR(200),
                venue_address TEXT,
                logo_url VARCHAR(500),
                primary_color VARCHAR(7) DEFAULT '#4e73df',
                secondary_color VARCHAR(7) DEFAULT '#858796',
                max_delegates INTEGER,
                is_active BOOLEAN DEFAULT 1,
                is_published BOOLEAN DEFAULT 0,
                custom_fields TEXT DEFAULT '[]',
                created_at DATETIME,
                updated_at DATETIME,
                created_by INTEGER
            )
        """)
        print("✓ Created events table")
    else:
        print("ℹ Events table already exists")
    
    # Check if pricing_tiers table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pricing_tiers'")
    if not cursor.fetchone():
        print("Creating pricing_tiers table...")
        cursor.execute("""
            CREATE TABLE pricing_tiers (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(200),
                price FLOAT NOT NULL,
                valid_from DATETIME,
                valid_until DATETIME,
                max_delegates INTEGER,
                group_min_size INTEGER,
                group_discount_percent FLOAT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME,
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
        """)
        print("✓ Created pricing_tiers table")
    else:
        print("ℹ Pricing_tiers table already exists")
    
    # Check if audit_logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
    if not cursor.fetchone():
        print("Creating audit_logs table...")
        cursor.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id INTEGER,
                description TEXT,
                old_values TEXT,
                new_values TEXT,
                ip_address VARCHAR(50),
                user_agent VARCHAR(500),
                event_id INTEGER,
                created_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
        """)
        print("✓ Created audit_logs table")
    else:
        print("ℹ Audit_logs table already exists")
    
    # Add event_id column to delegates if missing
    cursor.execute("PRAGMA table_info(delegates)")
    existing_delegate_columns = [col[1] for col in cursor.fetchall()]
    if 'event_id' not in existing_delegate_columns:
        try:
            cursor.execute("ALTER TABLE delegates ADD COLUMN event_id INTEGER")
            print("✓ Added column: delegates.event_id")
        except:
            print("ℹ Column event_id may already exist")
    
    conn.commit()
    conn.close()
    print("\n✓ Database migration complete!")
    print("\nNow reload your web app from PythonAnywhere's Web tab.")


if __name__ == '__main__':
    add_missing_columns()
