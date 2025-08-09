#!/usr/bin/env python3
"""Debug script to check TOTP encryption key configuration"""

import os
import sys
import django

sys.path.insert(0, '/home/ubuntu/repos/marketplace')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

django.setup()

from django.conf import settings
from cryptography.fernet import Fernet

print("=== TOTP Encryption Key Debug ===")
print(f"Django settings module: {settings.SETTINGS_MODULE}")

totp_key = getattr(settings, 'TOTP_ENCRYPTION_KEY', None)
print(f"TOTP_ENCRYPTION_KEY in settings: {totp_key is not None}")
print(f"TOTP_ENCRYPTION_KEY value: {repr(totp_key)}")

env_key = os.environ.get('TOTP_ENCRYPTION_KEY')
print(f"TOTP_ENCRYPTION_KEY in environment: {env_key is not None}")
print(f"Environment value: {repr(env_key)}")

if totp_key:
    try:
        if isinstance(totp_key, str):
            key_bytes = totp_key.encode()
        else:
            key_bytes = totp_key
        
        f = Fernet(key_bytes)
        test_data = b"test encryption"
        encrypted = f.encrypt(test_data)
        decrypted = f.decrypt(encrypted)
        print(f"✅ Fernet encryption test: SUCCESS")
        print(f"Test data: {test_data}")
        print(f"Decrypted: {decrypted}")
    except Exception as e:
        print(f"❌ Fernet encryption test: FAILED - {e}")

print("\n=== Django Settings Debug ===")
print(f"SECRET_KEY exists: {hasattr(settings, 'SECRET_KEY')}")
print(f"DEBUG: {settings.DEBUG}")
print(f"DATABASES configured: {bool(settings.DATABASES)}")
