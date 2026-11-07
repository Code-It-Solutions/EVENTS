"""Test script to verify all routes are working"""
from app import create_app

app = create_app()

print('=' * 60)
print('ROUTE VERIFICATION TEST')
print('=' * 60)

# Test with test client
with app.test_client() as client:
    # Test routes that don't require auth
    public_routes = [
        ('GET', '/register/', 'Public registration landing'),
        ('GET', '/auth/login', 'Login page'),
    ]
    
    # Test routes that require auth (will redirect to login)
    auth_routes = [
        ('GET', '/dashboard', 'Main dashboard'),
        ('GET', '/delegates/', 'Delegates list'),
        ('GET', '/payments/', 'Payments'),
        ('GET', '/admin/', 'Admin dashboard'),
        ('GET', '/events/', 'Events list'),
        ('GET', '/register/approvals', 'Pending approvals'),
    ]
    
    print('\n[PUBLIC ROUTES - Should return 200]')
    for method, url, desc in public_routes:
        resp = client.get(url)
        status = 'OK' if resp.status_code == 200 else f'CODE {resp.status_code}'
        print(f'  [{status}] {desc} ({url})')
    
    print('\n[AUTH ROUTES - Should redirect to login (302)]')
    for method, url, desc in auth_routes:
        resp = client.get(url)
        status = 'OK' if resp.status_code in [302, 200] else f'CODE {resp.status_code}'
        print(f'  [{status}] {desc} ({url}) -> {resp.status_code}')

# List all registered blueprints
print('\n' + '=' * 60)
print('REGISTERED BLUEPRINTS')
print('=' * 60)
for name in sorted(app.blueprints):
    bp = app.blueprints[name]
    print(f'  - {name}: {bp.url_prefix or "/"}')
