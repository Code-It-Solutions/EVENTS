"""
Migration script to add age_bracket column to delegates and pending_delegates tables.
Run this on PythonAnywhere after pulling the latest code:
    python add_age_bracket_migration.py
"""
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    # Check and add to delegates table
    print("Checking delegates table...")
    delegate_cols = [col['name'] for col in inspector.get_columns('delegates')]
    if 'age_bracket' not in delegate_cols:
        print("Adding age_bracket column to delegates table...")
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE delegates ADD COLUMN age_bracket VARCHAR(20)'))
            conn.commit()
        print("✓ Added age_bracket to delegates table")
    else:
        print("✓ age_bracket already exists in delegates table")
    
    # Check and add to pending_delegates table
    print("\nChecking pending_delegates table...")
    try:
        pending_cols = [col['name'] for col in inspector.get_columns('pending_delegates')]
        if 'age_bracket' not in pending_cols:
            print("Adding age_bracket column to pending_delegates table...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE pending_delegates ADD COLUMN age_bracket VARCHAR(20)'))
                conn.commit()
            print("✓ Added age_bracket to pending_delegates table")
        else:
            print("✓ age_bracket already exists in pending_delegates table")
    except Exception as e:
        print(f"Note: pending_delegates table check: {e}")
    
    print("\n=== Migration Complete ===")
    print("Please reload your web app from the PythonAnywhere Web tab.")
