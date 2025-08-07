#!/usr/bin/env python3
import requests
import json

def test_bitcoin_rpc():
    try:
        url = 'http://bitcoind:8332'
        auth = ('bitcoin_user', 'bitcoin_password')
        payload = {'method': 'getblockchaininfo', 'params': [], 'id': 1}
        
        response = requests.post(url, auth=auth, json=payload, timeout=10)
        print(f'Bitcoin RPC Status: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print(f'Bitcoin RPC Response: {json.dumps(result, indent=2)}')
            return True
        else:
            print(f'Bitcoin RPC Error: {response.text}')
            return False
            
    except Exception as e:
        print(f'Bitcoin RPC Connection Error: {e}')
        return False

def test_monero_daemon():
    try:
        url = 'http://monerod:18081/get_info'
        response = requests.get(url, timeout=10)
        print(f'Monero Daemon Status: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print(f'Monero Daemon Response: {json.dumps(result, indent=2)}')
            return True
        else:
            print(f'Monero Daemon Error: {response.text}')
            return False
            
    except Exception as e:
        print(f'Monero Daemon Connection Error: {e}')
        return False

def test_redis():
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 30)
        result = cache.get('test_key')
        print(f'Redis Test: {"SUCCESS" if result == "test_value" else "FAILED"}')
        return result == 'test_value'
    except Exception as e:
        print(f'Redis Connection Error: {e}')
        return False

if __name__ == '__main__':
    print("Testing RPC Connectivity...")
    print("=" * 50)
    
    bitcoin_ok = test_bitcoin_rpc()
    print()
    
    monero_ok = test_monero_daemon()
    print()
    
    redis_ok = test_redis()
    print()
    
    print("=" * 50)
    print(f"Bitcoin RPC: {'✓' if bitcoin_ok else '✗'}")
    print(f"Monero Daemon: {'✓' if monero_ok else '✗'}")
    print(f"Redis: {'✓' if redis_ok else '✗'}")
