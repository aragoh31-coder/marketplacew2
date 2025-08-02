#!/usr/bin/env python3
"""
Test the complete request flow to identify where blocking occurs
"""
import requests
import time

def test_request_patterns():
    """Test different request patterns to isolate blocking"""
    
    base_url = "http://localhost"
    
    test_cases = [
        {
            "name": "Minimal Request",
            "headers": {}
        },
        {
            "name": "Tor Browser Headers", 
            "headers": {
                "User-Agent": "Mozilla/5.0 (Android 10; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate"
            }
        },
        {
            "name": "Standard Browser Headers",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br"
            }
        }
    ]
    
    print("=== REQUEST FLOW TESTING ===")
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        try:
            response = requests.get(base_url, headers=test_case['headers'], timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            if response.status_code != 200:
                print(f"Response body: {response.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(1)  # Avoid rate limiting
    
    print("\n=== RAPID REQUEST TEST ===")
    print("Testing burst rate limiting:")
    for i in range(6):
        try:
            response = requests.get(base_url, headers=test_cases[1]['headers'], timeout=5)
            print(f"Request {i+1}: {response.status_code}")
        except Exception as e:
            print(f"Request {i+1}: Error - {e}")

if __name__ == "__main__":
    test_request_patterns()
