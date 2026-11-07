import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Determine base directory for PyInstaller compatibility
if getattr(sys, 'frozen', False):
    # Running as compiled exe - use exe's directory for database
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database path - always in instance folder next to exe/script
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_PATH, 'kayo.db')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    # Use absolute path for database to work with PyInstaller
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration for proper CSRF handling
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ['true', '1', 'yes']
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours session lifetime
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No expiration - token valid for entire session
    WTF_CSRF_SSL_STRICT = False  # Allow CSRF over HTTP for development
    
    # M-Pesa Daraja API Configuration
    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')
    MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE')  # Paybill Number
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY')
    MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL')
    MPESA_ENV = os.environ.get('MPESA_ENV', 'sandbox')  # 'sandbox' or 'production'
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # Email Configuration for OTP
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 'yes']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'KAYO Diocese of Nambale <noreply@kayo.org>')
    
    # OTP Settings
    OTP_REQUIRED_FOR_CHAIRS = os.environ.get('OTP_REQUIRED_FOR_CHAIRS', 'true').lower() in ['true', '1', 'yes']
    
    # Delegate registration fee (in KSh)
    DELEGATE_FEE = 1000
    REDUCED_FEE = 500  # For counsellors and intercessors
