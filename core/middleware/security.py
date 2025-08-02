import logging
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

try:
    import redis
    from ..utils.security import circuit_fingerprint
    r = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)
except ImportError:
    r = None
    circuit_fingerprint = None

class RateLimitMiddleware:
    """
    Redis-based rate limiting middleware that's Tor-friendly.
    Uses circuit fingerprinting instead of IP addresses.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if r is None or circuit_fingerprint is None:
            return self.get_response(request)
        
        if request.path.startswith('/anti_ddos/'):
            return self.get_response(request)
            
        fingerprint = circuit_fingerprint(request.META.get('HTTP_USER_AGENT', 'unknown'))
        key = f"rl:{fingerprint}"
        
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)  # 1-minute window
            if count > 20:  # 20 requests per minute
                return HttpResponseForbidden("Too many requests. Please wait before trying again.")
        except Exception as e:
            logger.warning(f"Rate limiting failed: {e}")
            pass
            
        return self.get_response(request)

class TorSecurityMiddleware:
    """
    Enhanced security middleware for Tor compatibility.
    """
    def __init__(self, get_response): 
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'none'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'none'; "
            "frame-src 'none'; "
            "object-src 'none';"
        )
        
        response['Referrer-Policy'] = 'no-referrer'
        response['X-Frame-Options'] = 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
