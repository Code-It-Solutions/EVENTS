"""Fix missing session_token column in users table"""
import sqlite3

conn = sqlite3.connect('instance/kayo.db')
cursor = conn.cursor()

# Check current columns in users table
cursor.execute('PRAGMA table_info(users)')
columns = [row[1] for row in cursor.fetchall()]
print('Current columns:', columns)

# Add missing columns if needed
if 'session_token' not in columns:
    cursor.execute('ALTER TABLE users ADD COLUMN session_token VARCHAR(100)')
    print('Added session_token column')
else:
    print('session_token already exists')

conn.commit()
conn.close()
print('Done!')
