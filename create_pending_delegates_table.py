"""
Script to create the pending_delegates table on production.
Run this on PythonAnywhere via the Bash console:
    python create_pending_delegates_table.py
"""
from app import create_app, db
from app.models.pending_delegate import PendingDelegate

app = create_app()

with app.app_context():
    # Create all missing tables
    db.create_all()
    print("✓ Database tables created/updated successfully!")
    
    # Verify the table exists
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    if 'pending_delegates' in tables:
        print("✓ pending_delegates table exists")
        
        # Show columns
        columns = [col['name'] for col in inspector.get_columns('pending_delegates')]
        print(f"  Columns: {columns}")
    else:
        print("✗ ERROR: pending_delegates table was NOT created")
