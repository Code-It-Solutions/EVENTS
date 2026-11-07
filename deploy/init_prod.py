"""Create tables and roles on first start. No default accounts: organisers sign up at /signup."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app, db
from app.models import Role

app = create_app()
with app.app_context():
    db.create_all()
    Role.create_default_roles()
    print('database ready')
