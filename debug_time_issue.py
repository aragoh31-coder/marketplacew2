#!/usr/bin/env python3
"""
Debug script to isolate the time comparison issue in verify_challenge
"""
import sys
import os
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

import django
django.setup()

from apps.anti_ddos.utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge
import time

def debug_time_issue():
    print("=== Creating challenge ===")
    challenge = create_challenge(0)
    print(f"Challenge created at: {challenge.created}")
    print(f"Min solve time: {challenge.mint}")
    print(f"Max solve time: {challenge.maxt}")
    
    serialized = serialize_challenge(challenge)
    decoded = decode_challenge(serialized)
    
    print(f"\nDecoded min solve time: {decoded.mint}")
    print(f"Decoded max solve time: {decoded.maxt}")
    
    start_time = int(time.time())
    current_time = time.time()
    
    print(f"\nStart time (int): {start_time}")
    print(f"Current time (float): {current_time}")
    print(f"Decoded mint (float): {decoded.mint}")
    print(f"Decoded maxt (float): {decoded.maxt}")
    
    print(f"\nTime checks:")
    print(f"start_time < decoded.mint: {start_time < decoded.mint}")
    print(f"current_time > decoded.maxt: {current_time > decoded.maxt}")
    
    if start_time < decoded.mint:
        wait_time = decoded.mint - start_time + 0.1
        print(f"Waiting {wait_time} seconds...")
        time.sleep(wait_time)
        
    corrected_start = int(decoded.mint) + 1
    print(f"\nTesting with corrected start time: {corrected_start}")
    result = verify_challenge(decoded, str(decoded.expected), corrected_start, ['', '', '', '', ''])
    print(f"Verification result: {result}")

if __name__ == "__main__":
    debug_time_issue()
