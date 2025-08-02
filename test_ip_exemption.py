#!/usr/bin/env python3
"""
Test script to verify FastPreFilterMiddleware IP exemption functionality
"""
import requests
import time
import sys

def test_private_ip_exemption():
    """Test that private IPs (like Docker containers) are never blocked"""
    print("=== TESTING PRIVATE IP EXEMPTION ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Android 10; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'X-Forwarded-For': '172.18.0.8'  # Simulate Tor container IP
    }
    
    success_count = 0
    total_requests = 100  # High volume to test exemption
    
    print(f"Sending {total_requests} rapid requests from private IP 172.18.0.8...")
    
    for i in range(total_requests):
        try:
            response = requests.get('http://localhost/', headers=headers, timeout=5)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code in [403, 429]:
                print(f"❌ FAILED: Request {i+1} blocked with status {response.status_code}")
                return False
            
            if i % 10 == 0:
                print(f"Progress: {i+1}/{total_requests} requests sent")
                
        except Exception as e:
            print(f"❌ Request {i+1} failed: {e}")
            return False
    
    print(f"✅ SUCCESS: All {success_count}/{total_requests} requests from private IP succeeded")
    return True

def test_public_ip_rate_limiting():
    """Test that public IPs still get rate limited"""
    print("\n=== TESTING PUBLIC IP RATE LIMITING ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'X-Forwarded-For': '8.8.8.8'  # Simulate public IP
    }
    
    print("Sending rapid requests from public IP 8.8.8.8 to trigger rate limiting...")
    
    blocked = False
    for i in range(80):  # Should exceed 50 + 20 burst limit
        try:
            response = requests.get('http://localhost/', headers=headers, timeout=5)
            
            if response.status_code in [403, 429]:
                print(f"✅ SUCCESS: Rate limiting triggered at request {i+1} (status {response.status_code})")
                blocked = True
                break
            elif response.status_code != 200:
                print(f"⚠️  Unexpected status {response.status_code} at request {i+1}")
                
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
    
    if not blocked:
        print("❌ FAILED: Public IP was not rate limited after 80 requests")
        return False
    
    return True

def test_loopback_exemption():
    """Test that loopback IPs are exempted"""
    print("\n=== TESTING LOOPBACK IP EXEMPTION ===")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    success_count = 0
    for i in range(30):  # Rapid requests to localhost
        try:
            response = requests.get('http://localhost/', headers=headers, timeout=5)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code in [403, 429]:
                print(f"❌ FAILED: Localhost blocked at request {i+1}")
                return False
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
    
    print(f"✅ SUCCESS: All {success_count}/30 localhost requests succeeded")
    return True

if __name__ == "__main__":
    print("FastPreFilterMiddleware IP Exemption Test Suite")
    print("=" * 50)
    
    test1_passed = test_private_ip_exemption()
    test2_passed = test_public_ip_rate_limiting()
    test3_passed = test_loopback_exemption()
    
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY:")
    print(f"Private IP Exemption: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Public IP Rate Limiting: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print(f"Loopback Exemption: {'✅ PASS' if test3_passed else '❌ FAIL'}")
    
    if all([test1_passed, test2_passed, test3_passed]):
        print("\n🎉 ALL TESTS PASSED - FastPreFilterMiddleware working correctly!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Check implementation")
        sys.exit(1)
