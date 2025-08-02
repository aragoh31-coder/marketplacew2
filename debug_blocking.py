#!/usr/bin/env python3
"""
Debug script to identify which Django middleware is blocking Tor requests
"""
import os
import sys
import django
from django.test import RequestFactory
from django.http import HttpResponse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
sys.path.append('/home/ubuntu/marketplace')
django.setup()

from django.conf import settings

def test_middleware_blocking():
    """Test each middleware individually to find the blocker"""
    
    factory = RequestFactory()
    request = factory.get('/')
    
    request.META.update({
        'HTTP_USER_AGENT': 'Mozilla/5.0 (Android 10; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
        'HTTP_X_FORWARDED_FOR': '172.18.0.8',
        'REMOTE_ADDR': '172.18.0.8',
        'HTTP_X_OPENRESTY_FILTERED': 'true',
        'HTTP_ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.5',
        'HTTP_ACCEPT_ENCODING': 'gzip, deflate'
    })
    
    print("=== TESTING INDIVIDUAL MIDDLEWARES ===")
    
    security_middlewares = [
        'apps.security.openresty_middleware.OpenRestyIntegrationMiddleware',
        'apps.security.resource_protection.ResourceProtectionMiddleware', 
        'apps.security.circuit_aware_defense.CircuitAwareDefense',
        'apps.security.fast_prefilter.FastPreFilterMiddleware',
        'apps.security.circuit_limiter.TorCircuitLimiter',
        'apps.security.optimized_middleware.OptimizedSecurityMiddleware'
    ]
    
    for middleware_path in security_middlewares:
        try:
            print(f"\n--- Testing {middleware_path.split('.')[-1]} ---")
            
            module_path, class_name = middleware_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            middleware_class = getattr(module, class_name)
            
            def mock_get_response(req):
                return HttpResponse("OK", status=200)
            
            middleware = middleware_class(mock_get_response)
            response = middleware(request)
            
            print(f"Status: {response.status_code}")
            if response.status_code == 403:
                print(f"🚨 BLOCKING MIDDLEWARE FOUND: {class_name}")
                print(f"Response: {response.content.decode()}")
                return class_name
            else:
                print(f"✅ {class_name} allows request")
                
        except Exception as e:
            print(f"❌ Error testing {middleware_path}: {e}")
    
    print("\n=== TESTING COMPLETE ===")
    return None

if __name__ == "__main__":
    blocking_middleware = test_middleware_blocking()
    if blocking_middleware:
        print(f"\n🎯 ROOT CAUSE: {blocking_middleware} is blocking Tor requests")
    else:
        print("\n❓ No blocking middleware found - issue may be elsewhere")
