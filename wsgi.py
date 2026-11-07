# WSGI entry point for PythonAnywhere
import sys
import os

# Add user site-packages to path (for pip --user installed packages)
user_site_packages = '/home/Monsiuer/.local/lib/python3.10/site-packages'
if user_site_packages not in sys.path:
    sys.path.insert(0, user_site_packages)

# Add your project directory to the sys.path
project_home = '/home/Monsiuer/KAYO'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(project_home, '.env')
load_dotenv(env_path)

# Import and create the Flask application
from app import create_app

application = create_app()
