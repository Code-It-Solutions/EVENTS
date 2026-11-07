import os
from dotenv import load_dotenv

load_dotenv()

print("M-Pesa Configuration Check")
print("=" * 50)
print(f"MPESA_ENV: {os.getenv('MPESA_ENV', 'not set')}")
print(f"MPESA_SHORTCODE: {os.getenv('MPESA_SHORTCODE', 'not set')}")
print(f"MPESA_CALLBACK_URL: {os.getenv('MPESA_CALLBACK_URL', 'not set')}")

key = os.getenv('MPESA_CONSUMER_KEY')
secret = os.getenv('MPESA_CONSUMER_SECRET')
passkey = os.getenv('MPESA_PASSKEY')

print(f"MPESA_CONSUMER_KEY: {key[:15] + '...' if key else 'NOT SET'}")
print(f"MPESA_CONSUMER_SECRET: {'configured' if secret else 'NOT SET'}")
print(f"MPESA_PASSKEY: {'configured' if passkey else 'NOT SET'}")

# Check database for payments
print("\n" + "=" * 50)
print("Database Payment Records")
print("=" * 50)

from app import create_app, db
from app.models.payment import Payment

app = create_app()
with app.app_context():
    total = Payment.query.count()
    print(f"Total payments: {total}")
    
    if total > 0:
        payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
        for p in payments:
            print(f"\nID: {p.id}")
            print(f"  Amount: KSh {p.amount}")
            print(f"  Mode: {p.payment_mode}")
            print(f"  Status: {p.status}")
            print(f"  Receipt: {p.mpesa_receipt_number}")
            print(f"  Phone: {p.phone_number}")
            print(f"  CheckoutRequestID: {p.checkout_request_id}")
            print(f"  Created: {p.created_at}")
