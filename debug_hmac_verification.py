#!/usr/bin/env python3
"""
Debug script to test HMAC verification logic step by step
"""
import sys
import os
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

import django
django.setup()

from apps.anti_ddos.utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge
import time
import base64
import json

def debug_verification():
    print("=== Creating challenge ===")
    challenge = create_challenge(0)
    print(f"Challenge: a={challenge.a}, b={challenge.b}, expected={challenge.expected}")
    print(f"Operation: {challenge.operation}")
    print(f"Created: {challenge.created}, mint: {challenge.mint}, maxt: {challenge.maxt}")
    
    print("\n=== Serializing challenge ===")
    serialized = serialize_challenge(challenge)
    print(f"Serialized length: {len(serialized)}")
    
    print("\n=== Decoding challenge ===")
    decoded = decode_challenge(serialized)
    if decoded:
        print(f"Decoded: a={decoded.a}, b={decoded.b}, expected={decoded.expected}")
        print(f"Operation: {getattr(decoded, 'operation', 'missing')}")
    else:
        print("Failed to decode challenge!")
        return
    
    print("\n=== Testing verification ===")
    start_time = int(time.time())
    answer = str(decoded.expected)
    honeypots = ['', '', '', '', '']
    
    print(f"Start time: {start_time}")
    print(f"Answer: {answer}")
    print(f"Current time: {time.time()}")
    print(f"Time check: start_time >= decoded.mint? {start_time >= decoded.mint}")
    print(f"Time check: current_time <= decoded.maxt? {time.time() <= decoded.maxt}")
    
    if start_time < decoded.mint:
        wait_time = decoded.mint - start_time
        print(f"Waiting {wait_time} seconds for minimum solve time...")
        time.sleep(wait_time + 0.1)
    
    result = verify_challenge(decoded, answer, start_time, honeypots)
    print(f"Verification result: {result}")
    
    if not result:
        print("\n=== Debugging verification failure ===")
        print(f"Challenge object exists: {decoded is not None}")
        print(f"Answer matches expected: {int(answer) == decoded.expected}")
        print(f"Honeypots empty: {all(not hp or not hp.strip() for hp in honeypots)}")
        
        from apps.anti_ddos.utils import hmac_sign
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
        print(f"HMAC signature matches: {expected_sig == decoded.hmac_sig}")

if __name__ == "__main__":
    debug_verification()
