#!/usr/bin/env python3
"""
Dedicated Tor PoW Launcher for Anti-DDoS Integration
Automatically solves PoW challenges and manages HMAC tokens
"""

import hashlib
import time
import random
import re
import base64
import json
import requests
import os
from stem import Signal
from stem.control import Controller
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOR_CONTROL_PORT = 9051
TOR_SOCKS_PORT = 9050
ONION_ADDRESS = os.getenv("CURRENT_ONION_ADDRESS", "*.onion")
CLEARNET_FALLBACK = "localhost"
MAX_RETRIES = 3
SOLVE_TIMEOUT = 30

class TorPowLauncher:
    def __init__(self):
        self.session = requests.Session()
        self.session.cookies.clear()
        original_request = self.session.request
        self.session.request = lambda *args, **kwargs: original_request(*args, timeout=SOLVE_TIMEOUT, **kwargs)
        
    def new_tor_circuit(self):
        """Create new Tor circuit for fresh identity"""
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as ctrl:
                ctrl.authenticate()
                ctrl.signal(Signal.NEWNYM)
                logger.info("Created new Tor circuit")
                time.sleep(2)  # Wait for circuit establishment
        except Exception as e:
            logger.warning(f"Failed to create new Tor circuit: {e}")
    
    def fetch_challenge(self, use_clearnet=False):
        """Fetch anti-DDoS challenge from onion service or clearnet fallback"""
        if use_clearnet:
            url = f"http://{CLEARNET_FALLBACK}/anti_ddos/challenge/"
            response = self.session.get(url, proxies={})
        else:
            url = f"http://{ONION_ADDRESS}/anti_ddos/challenge/"
            proxies = {
                'http': f'socks5h://localhost:{TOR_SOCKS_PORT}',
                'https': f'socks5h://localhost:{TOR_SOCKS_PORT}'
            }
            response = self.session.get(url, proxies=proxies)
        
        try:
            response.raise_for_status()
            html = response.text
            
            data_match = re.search(r'name="challenge_data" value="([^"]+)"', html)
            start_match = re.search(r'name="start_time" value="([^"]+)"', html)
            
            if not data_match or not start_match:
                logger.error("Could not extract challenge data from HTML")
                return None, None
                
            challenge_data = data_match.group(1)
            start_time = int(start_match.group(1))
            
            logger.info("Successfully fetched challenge")
            return challenge_data, start_time
            
        except Exception as e:
            logger.error(f"Failed to fetch challenge: {e}")
            return None, None
    
    def solve_math_challenge(self, html):
        """Solve the math problem from challenge HTML"""
        try:
            patterns = [
                r'What is (\d+) \+ (\d+)\?',
                r'What is (\d+) × (\d+)\?',
                r'What is (\d+) \* (\d+)\?',
                r'(\d+) \+ (\d+) =',
                r'(\d+) × (\d+) =',
                r'(\d+) \* (\d+) =',
                r'>What is (\d+) \+ (\d+)\?<',
                r'>What is (\d+) × (\d+)\?<'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    a, b = int(match.group(1)), int(match.group(2))
                    
                    if '+' in pattern:
                        result = a + b
                        logger.info(f"Solved addition: {a} + {b} = {result}")
                    else:  # multiplication
                        result = a * b
                        logger.info(f"Solved multiplication: {a} × {b} = {result}")
                    
                    return str(result)
            
            logger.warning("Could not find math problem in HTML, using fallback")
            numbers = re.findall(r'\b(\d+)\b', html)
            if len(numbers) >= 2:
                a, b = int(numbers[0]), int(numbers[1])
                if '×' in html or '*' in html:
                    result = a * b
                    logger.info(f"Fallback multiplication: {a} × {b} = {result}")
                else:
                    result = a + b
                    logger.info(f"Fallback addition: {a} + {b} = {result}")
                return str(result)
            
            logger.error("Could not solve math problem")
            return "42"  # Default fallback
            
        except Exception as e:
            logger.error(f"Failed to solve math challenge: {e}")
            return "42"
    
    def submit_solution(self, challenge_data, start_time, solution, use_clearnet=False):
        """Submit challenge solution and get HMAC token"""
        if use_clearnet:
            url = f"http://{CLEARNET_FALLBACK}/anti_ddos/verify/"
        else:
            url = f"http://{ONION_ADDRESS}/anti_ddos/verify/"
        
        logger.info(f"Using original start_time {start_time} for verification")
        
        data = {
            'challenge_data': challenge_data,
            'start_time': str(start_time),
            'answer': solution,
        }
        
        for i in range(5):
            data[f'hp{i}'] = ''
        
        try:
            if use_clearnet:
                response = self.session.post(url, data=data, allow_redirects=False, proxies={})
            else:
                proxies = {
                    'http': f'socks5h://localhost:{TOR_SOCKS_PORT}',
                    'https': f'socks5h://localhost:{TOR_SOCKS_PORT}'
                }
                response = self.session.post(url, data=data, allow_redirects=False, proxies=proxies)
            
            if response.cookies:
                logger.info(f"Received cookies: {list(response.cookies.keys())}")
            
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if location == '/' or location.endswith('/'):
                    logger.info("Challenge solved successfully! HMAC token received")
                    hmac_token = self.session.cookies.get('hmac_token')
                    if hmac_token:
                        logger.info(f"HMAC token stored in session: {len(hmac_token)} chars")
                    else:
                        logger.warning("No HMAC token found in session cookies")
                    return True
                else:
                    logger.warning(f"Challenge solution rejected - redirected to: {location}")
                    return False
            else:
                logger.error(f"Unexpected response status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to submit solution: {e}")
            return False
    
    def test_access(self, use_clearnet=False):
        """Test access to main site with HMAC token"""
        if use_clearnet:
            url = f"http://{CLEARNET_FALLBACK}/"
            response = self.session.get(url, allow_redirects=False, proxies={})
        else:
            url = f"http://{ONION_ADDRESS}/"
            proxies = {
                'http': f'socks5h://localhost:{TOR_SOCKS_PORT}',
                'https': f'socks5h://localhost:{TOR_SOCKS_PORT}'
            }
            response = self.session.get(url, allow_redirects=False, proxies=proxies)
        
        try:
            if response.status_code == 200:
                logger.info("Successfully accessed main site with HMAC token")
                return True
            elif response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'anti_ddos' in location:
                    logger.warning("Redirected back to anti-DDoS challenge")
                    return False
                else:
                    logger.info("Redirected to other page (likely success)")
                    return True
            else:
                logger.warning(f"Unexpected response status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to test access: {e}")
            return False
    
    def solve_challenge_from_data(self, challenge_data):
        """Solve challenge directly from challenge data instead of HTML parsing"""
        try:
            import base64
            import json
            decoded_data = json.loads(base64.b64decode(challenge_data).decode())
            
            a = decoded_data['a']
            b = decoded_data['b']
            operation = decoded_data.get('operation', '+')
            
            if operation == '+':
                result = a + b
                logger.info(f"Solved addition from data: {a} + {b} = {result}")
            else:  # multiplication
                result = a * b
                logger.info(f"Solved multiplication from data: {a} × {b} = {result}")
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Failed to solve challenge from data: {e}")
            return "42"  # Fallback
    
    def run_challenge_cycle(self, use_clearnet=False):
        """Run complete challenge-solve-verify cycle"""
        mode = "clearnet" if use_clearnet else "onion"
        logger.info(f"Starting PoW challenge cycle ({mode})")
        
        challenge_data, start_time = self.fetch_challenge(use_clearnet)
        if not challenge_data:
            return False
        
        solution = self.solve_challenge_from_data(challenge_data)
        
        try:
            import base64
            import json
            decoded_data = json.loads(base64.b64decode(challenge_data).decode())
            mint_time = decoded_data['mint']
            current_time = time.time()
            
            if current_time < mint_time:
                wait_time = mint_time - current_time + 0.1  # Add small buffer
                logger.info(f"Waiting {wait_time:.1f}s for minimum solve time (mint={mint_time})")
                time.sleep(wait_time)
        except Exception as e:
            logger.warning(f"Could not extract timing from challenge data: {e}")
            if start_time is not None:
                min_solve_time = start_time + 2  # 2 second minimum
                current_time = time.time()
                if current_time < min_solve_time:
                    wait_time = min_solve_time - current_time + 0.1  # Add small buffer
                    logger.info(f"Waiting {wait_time:.1f}s for minimum solve time")
                    time.sleep(wait_time)
        
        success = self.submit_solution(challenge_data, start_time, solution, use_clearnet)
        if not success:
            return False
        
        return self.test_access(use_clearnet)

def main():
    """Main launcher function"""
    launcher = TorPowLauncher()
    
    logger.info("Tor PoW Launcher starting...")
    logger.info(f"Target onion: {ONION_ADDRESS}")
    logger.info(f"Clearnet fallback: {CLEARNET_FALLBACK}")
    
    modes = [("clearnet", True), ("onion", False)]
    
    for mode_name, use_clearnet in modes:
        logger.info(f"\n=== Testing {mode_name.upper()} mode ===")
        
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"Attempt {attempt}/{MAX_RETRIES} ({mode_name})")
            
            if attempt > 1 and not use_clearnet:
                launcher.new_tor_circuit()
            
            try:
                success = launcher.run_challenge_cycle(use_clearnet)
                if success:
                    logger.info(f"✅ PoW challenge completed successfully via {mode_name}!")
                    logger.info("HMAC token obtained and verified")
                    return 0
                else:
                    logger.warning(f"❌ Attempt {attempt} failed ({mode_name})")
                    
            except Exception as e:
                logger.error(f"Attempt {attempt} failed with exception ({mode_name}): {e}")
            
            if attempt < MAX_RETRIES:
                wait_time = random.uniform(1, 3)
                logger.info(f"Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
        
        logger.warning(f"❌ All {mode_name} attempts failed")
    
    logger.error("❌ All modes failed")
    return 1

if __name__ == "__main__":
    exit(main())
