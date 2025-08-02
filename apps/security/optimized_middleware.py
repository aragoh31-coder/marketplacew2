import time
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings

class OptimizedSecurityMiddleware:
    """High-performance version of existing security middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.decision_cache = {}
        self.cache_timeout = 60  # Cache decisions for 1 minute
        
    def __call__(self, request):
        client_ip = self.get_client_ip(request)
        
        cache_key = self.get_request_signature(request)
        cached_decision = cache.get(f"sec_decision:{cache_key}")
        
        if cached_decision == 'block':
            return HttpResponse("Cached block", status=403)
        elif cached_decision == 'allow':
            return self.get_response(request)
        
        if self.should_block_request(request, client_ip):
            cache.set(f"sec_decision:{cache_key}", 'block', self.cache_timeout)
            return HttpResponse("Security block", status=403)
        
        cache.set(f"sec_decision:{cache_key}", 'allow', self.cache_timeout)
        return self.get_response(request)
    
    def get_request_signature(self, request):
        """Create signature for caching security decisions"""
        import hashlib
        signature_data = f"{request.path}|{request.method}|{self.get_client_ip(request)}"
        return hashlib.md5(signature_data.encode()).hexdigest()[:12]
    
    def get_client_ip(self, request):
        return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() 
                or request.META.get('REMOTE_ADDR', ''))
    
    def should_block_request(self, request, client_ip):
        """Optimized security evaluation"""
        
        if self.is_malformed_request(request):
            return True
        
        if self.is_suspicious_path(request.path):
            return True
        
        if self.exceeds_rate_limits(client_ip):
            return True
        
        if self.is_attack_pattern(request):
            return True
            
        return False
    
    def is_malformed_request(self, request):
        """Quick malformed request detection"""
        if len(request.path) > 2000:  # Extremely long paths
            return True
            
        if request.method not in ['GET', 'POST', 'HEAD', 'OPTIONS']:
            return True
            
        return False
    
    def is_suspicious_path(self, path):
        """Fast path-based blocking"""
        suspicious_patterns = [
            '/admin/', '/.env', '/wp-admin/', '/phpmyadmin/',
            '/config/', '/backup/', '/test/', '/debug/'
        ]
        
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in suspicious_patterns)
    
    def exceeds_rate_limits(self, client_ip):
        """Optimized rate limiting with multiple windows"""
        current_time = time.time()
        
        windows = [
            ('1min', 60, 15),    # 15 requests per minute
            ('5min', 300, 40),   # 40 requests per 5 minutes  
            ('1hour', 3600, 150) # 150 requests per hour
        ]
        
        for window_name, duration, limit in windows:
            if self.check_rate_window(client_ip, window_name, duration, limit, current_time):
                return True
                
        return False
    
    def check_rate_window(self, ip, window_name, duration, limit, current_time):
        """Efficient sliding window rate limiting"""
        cache_key = f"rate:{window_name}:{ip}"
        
        timestamps = cache.get(cache_key, [])
        
        timestamps = [t for t in timestamps if current_time - t < duration]
        
        if len(timestamps) >= limit:
            return True
        
        timestamps.append(current_time)
        
        cache.set(cache_key, timestamps, duration)
        return False
    
    def is_attack_pattern(self, request):
        """Detect common attack patterns"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        sql_patterns = ['union', 'select', 'drop', 'insert', 'delete', '--', ';']
        path_lower = request.path.lower()
        
        if any(pattern in path_lower for pattern in sql_patterns):
            return True
        
        if '<script' in path_lower or 'javascript:' in path_lower:
            return True
            
        return False
