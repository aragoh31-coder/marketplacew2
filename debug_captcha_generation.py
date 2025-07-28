#!/usr/bin/env python3
"""
Debug script to test CAPTCHA generation and identify image issues
"""
import os
import sys
import django

sys.path.append('/home/ubuntu/repos/marketplace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from apps.security.captcha_oneclick.utils import generate_captcha_with_tokens, make_cut_circle
import base64

def test_captcha_generation():
    print("🔍 Testing CAPTCHA Generation")
    print("=" * 50)
    
    try:
        print("1. Testing make_cut_circle function...")
        img_b64, missing = make_cut_circle()
        print(f"   ✅ Generated image for missing segment: {missing}")
        print(f"   ✅ Base64 length: {len(img_b64)}")
        print(f"   ✅ Base64 starts with: {img_b64[:50]}...")
        
        try:
            decoded = base64.b64decode(img_b64)
            print(f"   ✅ Base64 decoding successful, {len(decoded)} bytes")
        except Exception as e:
            print(f"   ❌ Base64 decoding failed: {e}")
        
        print("\n2. Testing generate_captcha_with_tokens function...")
        data = generate_captcha_with_tokens()
        print(f"   ✅ Generated CAPTCHA data:")
        print(f"   - Answer: {data['answer']}")
        print(f"   - Image length: {len(data['image'])}")
        print(f"   - HMAC token: {data['hmac_token'][:20]}...")
        print(f"   - Timestamp: {data['timestamp']}")
        print(f"   - PoW challenge: {data['pow_challenge']}")
        
        try:
            decoded = base64.b64decode(data['image'])
            print(f"   ✅ Image base64 decoding successful, {len(decoded)} bytes")
        except Exception as e:
            print(f"   ❌ Image base64 decoding failed: {e}")
            
        print("\n3. Testing data URL format...")
        data_url = f"data:image/png;base64,{data['image']}"
        print(f"   ✅ Data URL length: {len(data_url)}")
        print(f"   ✅ Data URL starts with: {data_url[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ CAPTCHA generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_captcha_generation()
    if success:
        print("\n🎯 CAPTCHA generation test completed successfully!")
    else:
        print("\n💥 CAPTCHA generation test failed!")
