"""
Script to save the KAYO and Diocese logos to the static images folder.

Since the logo images were provided in the chat, you need to manually save them:

1. KAYO Logo (green shield with Kenya map and cross):
   - Right-click on the KAYO logo image in the chat
   - Select "Save image as..."
   - Save it to: app/static/images/logo.png

2. ACK Diocese of Nambale Logo (coat of arms with bishop's mitre):
   - Right-click on the Diocese logo image in the chat
   - Select "Save image as..."
   - Save it to: app/static/images/diocese_logo.png

The logos should be PNG files with transparent background for best results.
"""

import os
import shutil
from pathlib import Path

# Define paths
BASE_DIR = Path(__file__).parent
STATIC_IMAGES = BASE_DIR / 'app' / 'static' / 'images'

# Ensure the images directory exists
STATIC_IMAGES.mkdir(parents=True, exist_ok=True)

print(f"Static images folder: {STATIC_IMAGES}")
print()

# Check for logos
logos = [
    ('logo.png', 'KAYO Logo (green shield)'),
    ('diocese_logo.png', 'ACK Diocese of Nambale Logo (coat of arms)')
]

for filename, description in logos:
    logo_path = STATIC_IMAGES / filename
    if logo_path.exists():
        print(f"✓ {description} found at {logo_path}")
    else:
        print(f"✗ {description} not found. Please save to {logo_path}")
        
        # Try common download locations
        common_paths = [
            Path.home() / 'Downloads' / filename,
            Path.home() / 'Desktop' / filename,
        ]
        
        for path in common_paths:
            if path.exists():
                shutil.copy(path, logo_path)
                print(f"  ✓ Found and copied from {path}")
                break
