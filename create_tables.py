#!/usr/bin/env python
"""Script to create all database tables and add missing columns"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    # Get database engine and inspector
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    
    print(f"Existing tables: {existing_tables}")
    
    # Check if session_token column exists in users table
    if 'users' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'session_token' not in columns:
            print("Adding session_token column to users table...")
            db.session.execute(text('ALTER TABLE users ADD COLUMN session_token VARCHAR(100)'))
            db.session.commit()
            print("session_token column added")
    
    # Import ALL models explicitly to register them with SQLAlchemy
    from app.models.user import User
    from app.models.delegate import Delegate
    from app.models.event import Event, PricingTier, CustomField
    from app.models.payment import Payment
    from app.models.audit import AuditLog, Role
    from app.models.permission_request import PermissionRequest
    from app.models.fund_management import (
        Pledge, PledgePayment, ScheduledPayment, 
        ScheduledPaymentInstallment, FundTransfer
    )
    from app.models.operations import CheckInSession, CheckIn, Announcement
    
    # Create all tables
    db.create_all()
    print("db.create_all() completed")
    
    # Verify tables
    inspector = inspect(db.engine)
    tables_after = inspector.get_table_names()
    print(f"Tables after create_all: {tables_after}")
    
    # Check specific tables
    required_tables = ['pledges', 'pledge_payments', 'scheduled_payments', 
                       'scheduled_payment_installments', 'fund_transfers']
    
    for table in required_tables:
        if table in tables_after:
            print(f"SUCCESS: {table} exists")
        else:
            print(f"WARNING: {table} does NOT exist")
    
    print("Done")
