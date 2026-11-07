"""
Add User Sessions Table
Run this script to create the user_sessions table for session management
"""
from app import create_app, db
from app.models.session import UserSession

app = create_app()

with app.app_context():
    # Create the user_sessions table if it doesn't exist
    try:
        db.create_all()
        print("✅ Database tables created/updated successfully!")
        
        # Verify the table exists
        result = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'"))
        if result.fetchone():
            print("✅ user_sessions table exists!")
        else:
            print("⚠️ user_sessions table not found - may need manual creation")
    except Exception as e:
        print(f"❌ Error: {e}")
