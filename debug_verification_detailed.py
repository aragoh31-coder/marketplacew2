#!/usr/bin/env python3
"""
Detailed debug script to identify why verify_challenge is failing
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

def debug_verification_step_by_step():
    print("=== Creating challenge and testing each verification step ===")
    
    challenge = create_challenge(0)
    print(f"Created challenge: a={challenge.a}, b={challenge.b}, expected={challenge.expected}")
    
    serialized = serialize_challenge(challenge)
    decoded = decode_challenge(serialized)
    print(f"Decoded challenge: a={decoded.a}, b={decoded.b}, expected={decoded.expected}")
    
    answer = str(decoded.expected)
    start_time = int(time.time())
    honeypots = ['', '', '', '', '']
    
    print(f"\n=== Step-by-step verification ===")
    print(f"Answer: {answer} (type: {type(answer)})")
    print(f"Expected: {decoded.expected} (type: {type(decoded.expected)})")
    print(f"Start time: {start_time} (type: {type(start_time)})")
    
    time.sleep(2.1)
    
    if not decoded:
        print("❌ Step 1 FAILED: Challenge is None")
        return
    print("✅ Step 1 PASSED: Challenge exists")
    
    now = time.time()
    start_time_float = float(start_time)
    print(f"Current time: {now}")
    print(f"Challenge mint: {decoded.mint}")
    print(f"Challenge maxt: {decoded.maxt}")
    print(f"Start time float: {start_time_float}")
    
    if start_time_float < decoded.mint:
        print("❌ Step 2 FAILED: Start time too early")
        return
    if now > decoded.maxt:
        print("❌ Step 2 FAILED: Challenge expired")
        return
    print("✅ Step 2 PASSED: Timing is correct")
    
    for i, hp_val in enumerate(honeypots):
        if hp_val and hp_val.strip():
            print(f"❌ Step 3 FAILED: Honeypot {i} has value: '{hp_val}'")
            return
    print("✅ Step 3 PASSED: All honeypots are empty")
    
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
    stored_sig = decoded.hmac_sig
    
    print(f"Expected signature: {expected_sig.hex()}")
    print(f"Stored signature: {stored_sig.hex()}")
    print(f"Signatures match: {hmac.compare_digest(expected_sig, stored_sig)}")
    
    if not hmac.compare_digest(expected_sig, stored_sig):
        print("❌ Step 4 FAILED: HMAC signature mismatch")
        return
    print("✅ Step 4 PASSED: HMAC signature is valid")
    
    try:
        user_answer = int(answer)
        expected_answer = decoded.expected
        print(f"User answer: {user_answer} (type: {type(user_answer)})")
        print(f"Expected answer: {expected_answer} (type: {type(expected_answer)})")
        print(f"Answers match: {user_answer == expected_answer}")
        
        if user_answer != expected_answer:
            print("❌ Step 5 FAILED: Answer mismatch")
            return
        print("✅ Step 5 PASSED: Answer is correct")
        
    except (ValueError, TypeError) as e:
        print(f"❌ Step 5 FAILED: Answer parsing error: {e}")
        return
    
    print(f"\n=== Final verification call ===")
    result = verify_challenge(decoded, answer, start_time, honeypots)
    print(f"verify_challenge result: {result}")
    
    if result:
        print("🎉 SUCCESS: All verification steps passed!")
    else:
        print("❌ FAILURE: verify_challenge returned False despite all steps passing")
        print("This indicates a bug in the verify_challenge function logic")

if __name__ == "__main__":
    debug_verification_step_by_step()
