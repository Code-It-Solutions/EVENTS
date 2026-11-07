#!/usr/bin/env python
"""Create the user_sessions table for session management"""

import sys
sys.path.insert(0, '.')

from app import create_app, db
from app.models.session import UserSession

app = create_app()

with app.app_context():
    # Create just the user_sessions table
    UserSession.__table__.create(db.engine, checkfirst=True)
    print("user_sessions table created successfully!")
    
    # Verify it exists
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'user_sessions' in tables:
        print("Verified: user_sessions table exists")
    else:
        print("ERROR: Table was not created")
