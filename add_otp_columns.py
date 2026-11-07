"""Add OTP columns to users table"""
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE users ADD COLUMN otp_code VARCHAR(6)'))
        print('Added otp_code column')
    except Exception as e:
        print(f'otp_code column may already exist: {e}')
    
    try:
        db.session.execute(text('ALTER TABLE users ADD COLUMN otp_expires_at DATETIME'))
        print('Added otp_expires_at column')
    except Exception as e:
        print(f'otp_expires_at column may already exist: {e}')
    
    db.session.commit()
    print('Database updated successfully!')
