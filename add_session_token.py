"""
Script to add session_token column to users table for single-session enforcement.
Run this once after updating the code:
    python add_session_token.py
"""

from app import create_app, db
from sqlalchemy import text

app = create_app()


def add_session_token_column():
    with app.app_context():
        try:
            # Check if column exists
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='session_token'"
            ))
            count = result.scalar()
            
            if count == 0:
                # Add the column
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN session_token VARCHAR(64)"
                ))
                db.session.commit()
                print("✓ Added session_token column to users table")
            else:
                print("ℹ session_token column already exists")
                
        except Exception as e:
            print(f"Error: {e}")
            # Try alternative method for other databases
            try:
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN session_token VARCHAR(64)"
                ))
                db.session.commit()
                print("✓ Added session_token column to users table")
            except Exception as e2:
                if 'duplicate column' in str(e2).lower() or 'already exists' in str(e2).lower():
                    print("ℹ session_token column already exists")
                else:
                    print(f"Error adding column: {e2}")


if __name__ == '__main__':
    add_session_token_column()
