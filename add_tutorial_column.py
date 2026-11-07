"""
Add has_seen_tutorial column to users table
Run this script once to add the column to existing databases
"""
import sqlite3
import os

def add_tutorial_column():
    # Try multiple possible database paths
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'instance', 'kayo.db'),
        os.path.join(os.path.dirname(__file__), 'instance', 'app.db'),
        '/home/monsiuer/KAYO/instance/kayo.db',  # PythonAnywhere path
        '/home/monsiuer/KAYO/instance/app.db',
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print(f"Database not found. Tried: {possible_paths}")
        return False
    
    print(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'has_seen_tutorial' in columns:
            print("Column 'has_seen_tutorial' already exists.")
            return True
        
        # Add the column
        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN has_seen_tutorial BOOLEAN DEFAULT 0
        """)
        
        conn.commit()
        print("Successfully added 'has_seen_tutorial' column to users table.")
        
        # Set has_seen_tutorial to True for existing approved users
        # so they don't get bombarded with tutorial on next login
        cursor.execute("""
            UPDATE users
            SET has_seen_tutorial = 1
            WHERE is_approved = 1
        """)
        conn.commit()
        print("Set has_seen_tutorial=True for existing approved users.")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    add_tutorial_column()
