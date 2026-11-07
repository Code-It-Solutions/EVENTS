"""
Fix existing users to be approved if they were created before approval system
Run this script to approve all existing users that don't have approval_status set
"""
import sqlite3
import os

def fix_existing_users():
    # Try multiple possible database paths
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'instance', 'kayo.db'),
        os.path.join(os.path.dirname(__file__), 'instance', 'app.db'),
        '/home/monsiuer/KAYO/instance/kayo.db',
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
        # Fix users that have NULL or empty approval_status
        # Approve all existing users (they were created before the approval system)
        cursor.execute("""
            UPDATE users
            SET is_approved = 1,
                approval_status = 'approved'
            WHERE approval_status IS NULL 
               OR approval_status = ''
               OR (is_approved IS NULL AND approval_status != 'pending' AND approval_status != 'rejected')
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        print(f"Fixed {updated_count} users with missing approval status.")
        
        # Show current user statuses
        cursor.execute("""
            SELECT name, email, role, is_approved, approval_status 
            FROM users
            ORDER BY id
        """)
        
        print("\nCurrent user statuses:")
        print("-" * 80)
        for row in cursor.fetchall():
            print(f"  {row[0]} ({row[1]}) - Role: {row[2]}, Approved: {row[3]}, Status: {row[4]}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    fix_existing_users()
