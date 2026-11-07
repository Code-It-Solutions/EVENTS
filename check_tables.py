"""Check database tables"""
import sqlite3

conn = sqlite3.connect('instance/kayo.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)

if 'pending_delegates' not in tables:
    print('\nWARNING: pending_delegates table does not exist!')
    print('Creating it now...')
    
    # Create the pending_delegates table
    from app import create_app, db
    app = create_app()
    with app.app_context():
        db.create_all()
    print('Table created!')
else:
    print('\npending_delegates table exists')

conn.close()
