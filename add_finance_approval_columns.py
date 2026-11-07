"""
Migration script to add finance approval columns to payments table.
Run this script on PythonAnywhere to update the database schema.
"""
import sqlite3
import os

# Database path - adjust for PythonAnywhere
DB_PATH = os.environ.get('DATABASE_PATH', 'instance/kayo.db')

def migrate():
    """Add finance approval columns to payments table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(payments)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    columns_to_add = [
        ("finance_status", "VARCHAR(20) DEFAULT 'approved'"),
        ("confirmed_by_chair_id", "INTEGER REFERENCES users(id)"),
        ("confirmed_by_chair_at", "DATETIME"),
        ("approved_by_finance_id", "INTEGER REFERENCES users(id)"),
        ("approved_by_finance_at", "DATETIME"),
        ("finance_notes", "TEXT"),
        ("rejection_reason", "TEXT"),
    ]
    
    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE payments ADD COLUMN {column_name} {column_type}"
                cursor.execute(sql)
                print(f"✓ Added column: {column_name}")
            except Exception as e:
                print(f"✗ Error adding {column_name}: {e}")
        else:
            print(f"- Column already exists: {column_name}")
    
    # Update existing payments to have 'approved' status (they were already processed)
    cursor.execute("""
        UPDATE payments 
        SET finance_status = 'approved' 
        WHERE finance_status IS NULL OR finance_status = ''
    """)
    print(f"✓ Updated {cursor.rowcount} existing payments to 'approved' status")
    
    conn.commit()
    conn.close()
    print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
