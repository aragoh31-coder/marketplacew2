#!/usr/bin/env python3
"""
Debug HMAC verification flow to identify why correct answers are being rejected
"""

import sys
import os
sys.path.append('/home/ubuntu/marketplace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

import django
django.setup()

from apps.anti_ddos.utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge
import time
import json

def test_challenge_flow():
    print("=== Testing HMAC Challenge Flow ===")
    
    print("1. Creating challenge...")
    challenge = create_challenge(difficulty=0)
    print(f"   Challenge: {challenge.a} + {challenge.b} = {challenge.expected}")
    print(f"   Created: {challenge.created}")
    print(f"   Min time: {challenge.mint}")
    print(f"   Max time: {challenge.maxt}")
    
    print("\n2. Serializing challenge...")
    serialized = serialize_challenge(challenge)
    print(f"   Serialized length: {len(serialized)}")
    
    print("\n3. Deserializing challenge...")
    decoded = decode_challenge(serialized)
    print(f"   Decoded: {decoded.a} + {decoded.b} = {decoded.expected}")
    print(f"   HMAC signatures match: {challenge.hmac_sig == decoded.hmac_sig}")
    
    print("\n4. Testing verification with correct answer...")
    correct_answer = str(challenge.expected)
    start_time = int(time.time())
    honeypots = ['', '', '', '', '']  # Empty honeypots
    
    print("   Waiting for minimum solve time...")
    while time.time() < challenge.mint:
        time.sleep(0.1)
    
    print(f"   Current time: {time.time()}")
    print(f"   Min time: {challenge.mint}")
    print(f"   Max time: {challenge.maxt}")
    
    result = verify_challenge(decoded, correct_answer, start_time, honeypots)
    print(f"   Verification result: {result}")
    
    print("\n5. Testing verification with wrong answer...")
    wrong_result = verify_challenge(decoded, "999", start_time, honeypots)
    print(f"   Wrong answer result: {wrong_result}")
    
    print("\n6. Manual HMAC signature verification...")
    from apps.anti_ddos.utils import hmac_sign
    import base64
    
    challenge_data = {
        'id': base64.b64encode(decoded.id).decode(),
        'created': decoded.created,
        'mint': decoded.mint,
        'maxt': decoded.maxt,
        'a': decoded.a,
        'b': decoded.b,
        'expected': decoded.expected,
        'difficulty': decoded.difficulty,
        'honeypots': decoded.honeypots
    }
    
    expected_sig = hmac_sign(challenge_data)
    print(f"   Expected sig: {expected_sig.hex()}")
    print(f"   Actual sig:   {decoded.hmac_sig.hex()}")
    print(f"   Signatures match: {expected_sig == decoded.hmac_sig}")
    
    return result

if __name__ == "__main__":
    test_challenge_flow()
