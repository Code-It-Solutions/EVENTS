# PythonAnywhere Deployment Guide for KAYO

## Step 1: Create a PythonAnywhere Account
1. Go to [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Sign up for a free "Beginner" account (or paid for custom domain)
3. Note your username - you'll need it for configuration

## Step 2: Upload Your Code

### Option A: Using Git (Recommended)
1. Open a **Bash console** from the PythonAnywhere dashboard
2. Clone your repository:
```bash
git clone https://github.com/blaire-glitch/KAYO.git
```

### Option B: Upload ZIP File
1. Zip your project folder (excluding `venv/` and `instance/`)
2. Go to **Files** tab on PythonAnywhere
3. Upload the zip file and extract it

## Step 3: Create Virtual Environment
In the Bash console:
```bash
cd KAYO
mkvirtualenv --python=/usr/bin/python3.10 kayo-venv
pip install -r requirements.txt
```

## Step 4: Configure Environment Variables
1. Create a `.env` file in your project directory:
```bash
cd ~/KAYO
nano .env
```

2. Add your configuration:
```
SECRET_KEY=your-super-secret-key-generate-a-random-one
DATABASE_URL=sqlite:////home/yourusername/KAYO/instance/kayo.db

# M-Pesa Daraja API (update with your credentials)
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_SHORTCODE=your-paybill-number
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://yourusername.pythonanywhere.com/payments/mpesa/callback
MPESA_ENV=sandbox
```

**Important:** Replace `yourusername` with your actual PythonAnywhere username!

To generate a secure secret key, run in Python:
```python
import secrets
print(secrets.token_hex(32))
```

## Step 5: Update wsgi.py
1. Go to **Files** tab
2. Navigate to `/home/yourusername/KAYO/wsgi.py`
3. Replace `yourusername` with your actual username:
```python
project_home = '/home/yourusername/KAYO'
```

## Step 6: Initialize the Database
In the Bash console:
```bash
cd ~/KAYO
workon kayo-venv
python init_db.py
```

## Step 7: Configure Web App
1. Go to the **Web** tab on PythonAnywhere
2. Click **Add a new web app**
3. Choose **Manual configuration** (NOT Flask)
4. Select **Python 3.10**

### Configure the Web App Settings:

**Source code:** `/home/yourusername/KAYO`

**Working directory:** `/home/yourusername/KAYO`

**WSGI configuration file:** Click the link and replace ALL content with:
```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/KAYO'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = os.path.join(project_home, '.env')
load_dotenv(env_path)

# Import and create the Flask application
from app import create_app

application = create_app()
```

**Virtualenv:** `/home/yourusername/.virtualenvs/kayo-venv`

### Static Files Mapping:
| URL | Directory |
|-----|-----------|
| /static/ | /home/yourusername/KAYO/app/static/ |

## Step 8: Reload Your Web App
1. Go to the **Web** tab
2. Click the green **Reload** button

## Step 9: Access Your App
Your app will be live at: `https://yourusername.pythonanywhere.com`

Default admin login:
- **Email:** admin@kayo.org
- **Password:** admin123

**⚠️ Change the admin password immediately after first login!**

---

## Troubleshooting

### View Error Logs
Go to **Web** tab → **Log files** section:
- **Error log** - Shows Python errors
- **Server log** - Shows web server issues
- **Access log** - Shows incoming requests

### Common Issues

#### 1. "Module not found" errors
```bash
workon kayo-venv
pip install -r requirements.txt
```
Then reload the web app.

#### 2. Database errors
```bash
cd ~/KAYO
workon kayo-venv
python init_db.py
```

#### 3. Static files not loading
Check the static files mapping in Web tab settings.

#### 4. 500 Internal Server Error
Check the error log for details. Common causes:
- Missing environment variables in `.env`
- Wrong paths in WSGI file
- Syntax errors in code

### Update Your App
When you push changes to GitHub:
```bash
cd ~/KAYO
git pull origin main
workon kayo-venv
pip install -r requirements.txt  # if dependencies changed
```
Then click **Reload** in the Web tab.

---

## M-Pesa Callback URL

For M-Pesa to work in production, you need to:
1. Register your callback URL with Safaricom
2. Update `.env` with the production callback URL:
```
MPESA_CALLBACK_URL=https://yourusername.pythonanywhere.com/payments/mpesa/callback
MPESA_ENV=production
```

**Note:** Free PythonAnywhere accounts have limited outbound internet access. 
M-Pesa API calls require a **paid account** for full functionality.

---

## Custom Domain (Paid Accounts Only)

1. Go to **Web** tab
2. Add your custom domain (e.g., `kayo.yourchurch.org`)
3. Update DNS settings with your domain registrar
4. Update `MPESA_CALLBACK_URL` in `.env` to use the new domain
