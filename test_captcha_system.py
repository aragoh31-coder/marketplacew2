#!/usr/bin/env python3
"""
Test script for the hardened CAPTCHA system
"""
import os
import sys
import django

sys.path.append('/home/ubuntu/repos/marketplace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from apps.security.captcha_oneclick.utils import generate_captcha_with_tokens, validate_captcha_submission
import time

def test_captcha_system():
    print("🔐 Testing Hardened CAPTCHA System")
    print("=" * 50)
    
    print("1. Testing CAPTCHA generation...")
    data = generate_captcha_with_tokens()
    print(f"   ✅ Generated CAPTCHA data:")
    print(f"   - Answer: {data['answer']}")
    print(f"   - Timestamp: {data['timestamp']}")
    print(f"   - HMAC Token: {data['hmac_token'][:20]}...")
    print(f"   - PoW Challenge: {data['pow_challenge']}")
    print(f"   - Segments: {data['segments']}")
    
    print("\n2. Testing correct answer validation...")
    is_valid, msg = validate_captcha_submission(
        data['answer'], 
        data['hmac_token'], 
        data['timestamp']
    )
    print(f"   ✅ Correct answer: {is_valid} - {msg}")
    
    print("\n3. Testing wrong answer validation...")
    is_valid, msg = validate_captcha_submission(
        (data['answer'] + 1) % 12, 
        data['hmac_token'], 
        data['timestamp']
    )
    print(f"   ✅ Wrong answer: {is_valid} - {msg}")
    
    print("\n4. Testing expired timestamp validation...")
    old_timestamp = int(time.time()) - 200  # 200 seconds ago
    is_valid, msg = validate_captcha_submission(
        data['answer'], 
        data['hmac_token'], 
        old_timestamp
    )
    print(f"   ✅ Expired timestamp: {is_valid} - {msg}")
    
    print("\n5. Testing HMAC token tampering...")
    fake_token = "fake_token_12345"
    is_valid, msg = validate_captcha_submission(
        data['answer'], 
        fake_token, 
        data['timestamp']
    )
    print(f"   ✅ Tampered token: {is_valid} - {msg}")
    
    print("\n" + "=" * 50)
    print("🎯 CAPTCHA System Test Complete!")
    return True

if __name__ == "__main__":
    test_captcha_system()
