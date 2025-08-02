#!/usr/bin/env python3
"""
Debug the exact parameters being passed to verify_challenge in views.py
"""

import sys
import os
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

import django
django.setup()

from apps.anti_ddos.utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge
import time
import json

def test_views_verification_flow():
    print("=== Testing Views.py Verification Flow ===")
    
    print("1. Creating and serializing challenge (like challenge_view)...")
    challenge = create_challenge(0)
    challenge_data = serialize_challenge(challenge)
    start_time = int(time.time())
    
    print(f"   Challenge: {challenge.a} + {challenge.b} = {challenge.expected}")
    print(f"   Start time: {start_time}")
    print(f"   Challenge mint: {challenge.mint}")
    print(f"   Challenge maxt: {challenge.maxt}")
    
    print("\n2. Waiting for minimum solve time...")
    while time.time() < challenge.mint:
        time.sleep(0.1)
    
    print("\n3. Simulating views.py verification...")
    decoded_challenge = decode_challenge(challenge_data)
    answer = str(challenge.expected)
    honeypots = ['', '', '', '', '']
    
    current_time = time.time()
    print(f"   Current time: {current_time}")
    print(f"   Decoded mint: {decoded_challenge.mint}")
    print(f"   Decoded maxt: {decoded_challenge.maxt}")
    print(f"   Time check passed: {current_time >= decoded_challenge.mint and current_time <= decoded_challenge.maxt}")
    
    verification_result = verify_challenge(decoded_challenge, answer, start_time, honeypots)
    print(f"   Verification result: {verification_result}")
    
    print("\n4. Testing verification without start_time parameter...")
    verification_result_no_start = verify_challenge(decoded_challenge, answer, None, honeypots)
    print(f"   Verification result (no start_time): {verification_result_no_start}")
    
    return verification_result

if __name__ == "__main__":
    test_views_verification_flow()
