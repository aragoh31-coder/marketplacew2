#!/usr/bin/env python
import os
import sys
import django

sys.path.append('/home/ubuntu/repos/marketplace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from accounts.totp_utils import TOTPManager

def test_totp_functionality():
    """Test TOTP utilities functionality"""
    print("Testing TOTP functionality...")
    
    totp_manager = TOTPManager()
    secret = totp_manager.generate_secret()
    print(f"Generated TOTP secret: {secret}")
    
    current_code = totp_manager.get_current_code(secret)
    print(f"Current TOTP code: {current_code}")
    
    is_valid = totp_manager.verify_code(secret, current_code)
    print(f"TOTP verification result: {is_valid}")
    
    backup_codes = totp_manager.generate_backup_codes(5)
    print(f"Generated backup codes: {backup_codes}")
    
    print("TOTP functionality test completed successfully!")

if __name__ == "__main__":
    test_totp_functionality()
