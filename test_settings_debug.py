#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, '/app')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

try:
    print("Testing Django settings module import...")
    
    import marketplace.settings as settings_module
    print("✓ Settings module imported successfully")
    
    print(f"ROOT_URLCONF in module: {hasattr(settings_module, 'ROOT_URLCONF')}")
    
    if hasattr(settings_module, 'ROOT_URLCONF'):
        print(f"ROOT_URLCONF value: {settings_module.ROOT_URLCONF}")
    else:
        print("Available attributes:", [attr for attr in dir(settings_module) if not attr.startswith('_')])
    
    import django
    django.setup()
    print("✓ Django setup completed")
    
    from django.conf import settings
    root_urlconf = getattr(settings, 'ROOT_URLCONF', 'NOT_FOUND')
    print(f"Django conf ROOT_URLCONF: {root_urlconf}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
