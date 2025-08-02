#!/usr/bin/env python3
"""
Debug script to isolate the verify_challenge function failure
"""
import sys
import os
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

import django
django.setup()

from apps.anti_ddos.utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge, hmac_sign
import time
import base64
import json
import hmac

def debug_verify_challenge():
    print("=== Creating and testing challenge verification ===")
    
    challenge = create_challenge(0)
    print(f"Original challenge: a={challenge.a}, b={challenge.b}, expected={challenge.expected}")
    print(f"Operation: {getattr(challenge, 'operation', 'missing')}")
    print(f"Created: {challenge.created}, mint: {challenge.mint}, maxt: {challenge.maxt}")
    
    serialized = serialize_challenge(challenge)
    decoded = decode_challenge(serialized)
    print(f"\nDecoded challenge: a={decoded.a}, b={decoded.b}, expected={decoded.expected}")
    
    start_time = int(time.time())
    answer = str(decoded.expected)
    honeypots = ['', '', '', '', '']
    
    print(f"\n=== Testing verification components ===")
    print(f"Answer: {answer} (type: {type(answer)})")
    print(f"Expected: {decoded.expected} (type: {type(decoded.expected)})")
    print(f"Answer matches: {int(answer) == decoded.expected}")
    
    current_time = time.time()
    if current_time < decoded.mint:
        wait_time = decoded.mint - current_time + 0.1
        print(f"Waiting {wait_time:.1f} seconds for minimum solve time...")
        time.sleep(wait_time)
    
    verification_start = max(start_time, int(decoded.mint))
    print(f"Verification start: {verification_start}")
    print(f"Current time: {time.time()}")
    print(f"Time check: {verification_start >= decoded.mint and time.time() <= decoded.maxt}")
    
    honeypot_check = all(not hp or not hp.strip() for hp in honeypots)
    print(f"Honeypot check passed: {honeypot_check}")
    
    print(f"\n=== Testing HMAC signature verification ===")
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
    
    print(f"Challenge data for HMAC: {challenge_data}")
    
    expected_sig = hmac_sign(challenge_data)
    stored_sig = decoded.hmac_sig
    
    print(f"Expected signature length: {len(expected_sig)}")
    print(f"Stored signature length: {len(stored_sig)}")
    print(f"Expected signature (hex): {expected_sig.hex()}")
    print(f"Stored signature (hex): {stored_sig.hex()}")
    print(f"Signatures match: {hmac.compare_digest(expected_sig, stored_sig)}")
    
    print(f"\n=== Final verification test ===")
    result = verify_challenge(decoded, answer, verification_start, honeypots)
    print(f"verify_challenge result: {result}")
    
    print(f"\n=== Testing with original challenge object ===")
    result_orig = verify_challenge(challenge, answer, verification_start, honeypots)
    print(f"verify_challenge with original: {result_orig}")

if __name__ == "__main__":
    debug_verify_challenge()
