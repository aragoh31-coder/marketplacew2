#!/usr/bin/env python3
import os
import sys

# Add the project directory to Python path
sys.path.insert(0, '/app')

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

try:
    print("Testing Django settings loading...")
    
    # Try to import Django and setup
    import django
    print("✓ Django imported successfully")
    
    # Try to setup Django
    django.setup()
    print("✓ Django setup completed")
    
    # Try to access settings
    from django.conf import settings
    print("✓ Django settings imported")
    
    # Check if ROOT_URLCONF exists
    root_urlconf = getattr(settings, 'ROOT_URLCONF', 'NOT_FOUND')
    print(f"ROOT_URLCONF: {root_urlconf}")
    
    # Check other essential settings
    installed_apps = getattr(settings, 'INSTALLED_APPS', 'NOT_FOUND')
    print(f"INSTALLED_APPS count: {len(installed_apps) if installed_apps != 'NOT_FOUND' else 'NOT_FOUND'}")
    
    databases = getattr(settings, 'DATABASES', 'NOT_FOUND')
    print(f"DATABASES: {databases}")
    
    print("✓ All Django settings loaded successfully")
    
except Exception as e:
    print(f"✗ Error loading Django settings: {e}")
    import traceback
    traceback.print_exc()
