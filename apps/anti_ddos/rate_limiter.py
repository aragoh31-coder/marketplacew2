import time
import hashlib
from django.core.cache import cache
from django.conf import settings
from core.utils.security import circuit_fingerprint


class RateLimiter:
    """
    Comprehensive rate limiting system for anti-DDoS protection.
    Supports both IP-based and circuit fingerprint-based limiting for Tor users.
    """
    
    def __init__(self):
        self.limits = {
            'global': {'requests': 100, 'window': 3600},  # 100 requests per hour
            'challenge': {'requests': 10, 'window': 300},  # 10 challenges per 5 minutes
            'auth': {'requests': 5, 'window': 900},        # 5 auth attempts per 15 minutes
        }
    
    def get_client_id(self, request):
        """Generate unique client identifier"""
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        
        if '.onion' in request.get_host():
            return f"circuit:{circuit_fingerprint(user_agent)}"
        
        ip = self._get_client_ip(request)
        client_data = f"{ip}:{user_agent}"
        return f"ip:{hashlib.sha256(client_data.encode()).hexdigest()[:16]}"
    
    def _get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def is_rate_limited(self, request, limit_type='global'):
        """Check if client has exceeded rate limit"""
        client_id = self.get_client_id(request)
        limit_config = self.limits.get(limit_type, self.limits['global'])
        
        cache_key = f"rate_limit:{limit_type}:{client_id}"
        
        current_data = cache.get(cache_key, {'count': 0, 'window_start': time.time()})
        current_time = time.time()
        
        if current_time - current_data['window_start'] > limit_config['window']:
            current_data = {'count': 0, 'window_start': current_time}
        
        if current_data['count'] >= limit_config['requests']:
            return True
        
        current_data['count'] += 1
        cache.set(cache_key, current_data, limit_config['window'])
        
        return False
    
    def get_remaining_requests(self, request, limit_type='global'):
        """Get number of remaining requests for client"""
        client_id = self.get_client_id(request)
        limit_config = self.limits.get(limit_type, self.limits['global'])
        
        cache_key = f"rate_limit:{limit_type}:{client_id}"
        current_data = cache.get(cache_key, {'count': 0, 'window_start': time.time()})
        
        return max(0, limit_config['requests'] - current_data['count'])
    
    def block_client(self, request, duration=3600):
        """Temporarily block a client"""
        client_id = self.get_client_id(request)
        cache_key = f"blocked:{client_id}"
        cache.set(cache_key, True, duration)
    
    def is_blocked(self, request):
        """Check if client is temporarily blocked"""
        client_id = self.get_client_id(request)
        cache_key = f"blocked:{client_id}"
        return cache.get(cache_key, False)
