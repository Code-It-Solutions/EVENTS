"""
KAYO Desktop Application
Launches the KAYO Flask app in a native desktop window.
"""
import sys
import os
import traceback

print("="*60)
print("KAYO Desktop Application - Starting...")
print("="*60)

# Handle PyInstaller bundled environment
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
    # Set the working directory to where the exe is located for database access
    os.chdir(EXE_DIR)
    print(f"Running as EXE")
    print(f"Bundle directory: {BASE_DIR}")
    print(f"EXE directory: {EXE_DIR}")
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR
    print(f"Running as script")
    print(f"Script directory: {BASE_DIR}")

print(f"Working directory: {os.getcwd()}")

# Ensure the app directory is in path
sys.path.insert(0, BASE_DIR)

# Set environment variable for Flask to find templates
os.environ['FLASK_APP_BASE'] = BASE_DIR

# Try imports with detailed error reporting
print("\nLoading dependencies...")
try:
    import webbrowser
    print("  - webbrowser: OK")
except ImportError as e:
    print(f"  - webbrowser: FAILED - {e}")

try:
    import threading
    print("  - threading: OK")
except ImportError as e:
    print(f"  - threading: FAILED - {e}")

try:
    import time
    print("  - time: OK")
except ImportError as e:
    print(f"  - time: FAILED - {e}")

try:
    from werkzeug.security import generate_password_hash
    print("  - werkzeug: OK")
except ImportError as e:
    print(f"  - werkzeug: FAILED - {e}")
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)

try:
    from flask import Flask
    print("  - flask: OK")
except ImportError as e:
    print(f"  - flask: FAILED - {e}")
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)

try:
    from app import create_app, db
    print("  - app module: OK")
except ImportError as e:
    print(f"  - app module: FAILED - {e}")
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)

try:
    from app.models import User
    print("  - app.models: OK")
except ImportError as e:
    print(f"  - app.models: FAILED - {e}")
    traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)

print("\nAll dependencies loaded successfully!")


def open_browser(port):
    """Open browser after a short delay."""
    time.sleep(2)
    try:
        webbrowser.open(f'http://127.0.0.1:{port}')
    except Exception as e:
        print(f"Could not open browser: {e}")


def main():
    """Launch KAYO as a desktop application."""
    try:
        # Create the Flask app
        print("\nCreating Flask app...")
        app = create_app()
        print("Flask app created!")
        
        # Override template and static folders for PyInstaller
        if getattr(sys, 'frozen', False):
            app.template_folder = os.path.join(BASE_DIR, 'app', 'templates')
            app.static_folder = os.path.join(BASE_DIR, 'app', 'static')
            print(f"Template folder: {app.template_folder}")
            print(f"Static folder: {app.static_folder}")
        
        # Ensure instance folder exists
        instance_path = os.path.join(EXE_DIR, 'instance')
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)
            print(f"Created instance folder: {instance_path}")
        
        # Ensure database tables exist and create default admin
        print("\nSetting up database...")
        with app.app_context():
            db.create_all()
            print("Database tables verified/created.")
            
            # Create default admin if no users exist
            try:
                user_count = User.query.count()
                print(f"Existing users: {user_count}")
                if user_count == 0:
                    admin = User(
                        name='Admin',
                        email='admin@kayo.com',
                        phone='0700000000',
                        role='admin',
                        password_hash=generate_password_hash('admin123'),
                        is_approved=True,
                        approval_status='approved',
                        is_active=True
                    )
                    db.session.add(admin)
                    db.session.commit()
                    print("Default admin created: admin@kayo.com / admin123")
            except Exception as e:
                print(f"Warning: Could not check/create admin user: {e}")
        
        port = 5000
        print(f"\n{'='*60}")
        print("KAYO Desktop Application - READY")
        print(f"{'='*60}")
        print(f"Server URL: http://127.0.0.1:{port}")
        print(f"Login: admin@kayo.com / admin123")
        print(f"{'='*60}")
        print("Opening browser in 2 seconds...")
        print("Keep this window open while using KAYO.")
        print("Press Ctrl+C to stop the server.")
        print(f"{'='*60}\n")
        
        # Open browser in background thread
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        
        # Run Flask server
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"STARTUP ERROR")
        print(f"{'='*60}")
        print(f"Error: {e}")
        print(f"\nFull traceback:")
        traceback.print_exc()
        print(f"\n{'='*60}")
        print("Please report this error.")
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"\nFatal error: {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
