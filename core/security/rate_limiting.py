import time
import hashlib
from django.core.cache import cache
from django.http import HttpResponse
from functools import wraps
import logging

logger = logging.getLogger('security.ratelimit')


class EnterpriseRateLimiter:
    """Advanced rate limiting with multiple strategies and privacy protection"""
    
    def __init__(self):
        self.default_limits = {
            'login': {'attempts': 5, 'window': 900, 'cooldown': 900},  # 5 attempts per 15 min, 15 min cooldown
            'registration': {'attempts': 3, 'window': 3600, 'cooldown': 3600},  # 3 attempts per hour
            'password_reset': {'attempts': 3, 'window': 1800, 'cooldown': 3600},  # 3 per 30 min
            'form_submit': {'attempts': 10, 'window': 300, 'cooldown': 300},  # 10 per 5 min
            'api_call': {'attempts': 100, 'window': 3600, 'cooldown': 60},  # 100 per hour
            'withdrawal': {'attempts': 5, 'window': 3600, 'cooldown': 3600},  # 5 per hour
            'file_upload': {'attempts': 5, 'window': 1800, 'cooldown': 1800},  # 5 per 30 min
            'message_send': {'attempts': 20, 'window': 3600, 'cooldown': 300},  # 20 per hour
            'pgp_challenge': {'attempts': 10, 'window': 1800, 'cooldown': 900},  # 10 per 30 min
        }
    
    def _get_client_identifier(self, request):
        """Get privacy-preserving client identifier for Tor compatibility"""
        # For authenticated users, use user ID
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # For anonymous users, use session key if available
        if hasattr(request, 'session') and request.session.session_key:
            return f"session:{request.session.session_key}"
        
        # Fallback to user agent hash (less reliable but privacy-preserving)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]
        return f"ua:{ua_hash}"
    
    def is_rate_limited(self, request, action, custom_limits=None):
        """Check if request is rate limited"""
        limits = custom_limits or self.default_limits.get(action, self.default_limits['form_submit'])
        
        client_id = self._get_client_identifier(request)
        cache_key = f"rate_limit:{action}:{client_id}"
        
        current_time = time.time()
        
        # Get existing attempts
        attempts_data = cache.get(cache_key, [])
        
        # Clean old attempts outside the window
        window_start = current_time - limits['window']
        attempts_data = [attempt_time for attempt_time in attempts_data if attempt_time > window_start]
        
        # Check if limit exceeded
        if len(attempts_data) >= limits['attempts']:
            logger.warning(f"Rate limit exceeded for {action} by {client_id}")
            return True, limits['cooldown']
        
        return False, 0
    
    def record_attempt(self, request, action, custom_limits=None):
        """Record an attempt for rate limiting"""
        limits = custom_limits or self.default_limits.get(action, self.default_limits['form_submit'])
        
        client_id = self._get_client_identifier(request)
        cache_key = f"rate_limit:{action}:{client_id}"
        
        current_time = time.time()
        
        # Get existing attempts
        attempts_data = cache.get(cache_key, [])
        
        # Add current attempt
        attempts_data.append(current_time)
        
        # Clean old attempts and store
        window_start = current_time - limits['window']
        attempts_data = [attempt_time for attempt_time in attempts_data if attempt_time > window_start]
        
        # Store with expiry
        cache.set(cache_key, attempts_data, timeout=limits['window'])
        
        logger.debug(f"Recorded {action} attempt for {client_id}: {len(attempts_data)}/{limits['attempts']}")
    
    def reset_attempts(self, request, action):
        """Reset rate limit attempts (e.g., after successful authentication)"""
        client_id = self._get_client_identifier(request)
        cache_key = f"rate_limit:{action}:{client_id}"
        cache.delete(cache_key)
        logger.info(f"Reset rate limit attempts for {action} by {client_id}")
    
    def get_remaining_attempts(self, request, action, custom_limits=None):
        """Get remaining attempts before rate limit"""
        limits = custom_limits or self.default_limits.get(action, self.default_limits['form_submit'])
        
        client_id = self._get_client_identifier(request)
        cache_key = f"rate_limit:{action}:{client_id}"
        
        current_time = time.time()
        
        # Get existing attempts
        attempts_data = cache.get(cache_key, [])
        
        # Clean old attempts outside the window
        window_start = current_time - limits['window']
        attempts_data = [attempt_time for attempt_time in attempts_data if attempt_time > window_start]
        
        remaining = max(0, limits['attempts'] - len(attempts_data))
        return remaining
    
    def get_cooldown_remaining(self, request, action, custom_limits=None):
        """Get remaining cooldown time"""
        limits = custom_limits or self.default_limits.get(action, self.default_limits['form_submit'])
        
        client_id = self._get_client_identifier(request)
        cache_key = f"rate_limit:{action}:{client_id}"
        
        current_time = time.time()
        
        # Get existing attempts
        attempts_data = cache.get(cache_key, [])
        
        # Clean old attempts outside the window
        window_start = current_time - limits['window']
        attempts_data = [attempt_time for attempt_time in attempts_data if attempt_time > window_start]
        
        if len(attempts_data) >= limits['attempts']:
            # Find the oldest attempt in the current window
            oldest_attempt = min(attempts_data)
            cooldown_end = oldest_attempt + limits['cooldown']
            remaining_cooldown = max(0, cooldown_end - current_time)
            return remaining_cooldown
        
        return 0


def rate_limit(action=None, **limit_kwargs):
    """Decorator for rate limiting views"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            limiter = EnterpriseRateLimiter()
            action_name = action or view_func.__name__
            
            # Check rate limit
            is_limited, cooldown = limiter.is_rate_limited(request, action_name, limit_kwargs)
            
            if is_limited:
                # Return rate limit response
                response = HttpResponse(
                    f"Rate limit exceeded. Try again in {int(cooldown)} seconds.",
                    status=429,
                    content_type='text/plain'
                )
                response['Retry-After'] = str(int(cooldown))
                response['X-RateLimit-Limit'] = str(limit_kwargs.get('attempts', 10))
                response['X-RateLimit-Remaining'] = '0'
                response['X-RateLimit-Reset'] = str(int(time.time() + cooldown))
                
                logger.warning(f"Rate limit response sent for {action_name}")
                return response
            
            # Record the attempt
            limiter.record_attempt(request, action_name, limit_kwargs)
            
            # Call the original view
            response = view_func(request, *args, **kwargs)
            
            # Add rate limit headers to successful responses
            remaining = limiter.get_remaining_attempts(request, action_name, limit_kwargs)
            response['X-RateLimit-Limit'] = str(limit_kwargs.get('attempts', 10))
            response['X-RateLimit-Remaining'] = str(remaining)
            
            return response
        
        return wrapper
    return decorator


def check_rate_limit(request, action, custom_limits=None):
    """Utility function to check rate limit in views"""
    limiter = EnterpriseRateLimiter()
    is_limited, cooldown = limiter.is_rate_limited(request, action, custom_limits)
    
    if not is_limited:
        limiter.record_attempt(request, action, custom_limits)
    
    return not is_limited, cooldown


def reset_rate_limit(request, action):
    """Utility function to reset rate limit (e.g., after successful auth)"""
    limiter = EnterpriseRateLimiter()
    limiter.reset_attempts(request, action)


class GlobalRateLimitMiddleware:
    """Global rate limiting middleware for all requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.limiter = EnterpriseRateLimiter()
        
        # Global limits per client
        self.global_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
        }
    
    def __call__(self, request):
        # Skip rate limiting for static files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)
        
        # Check global rate limits
        client_id = self.limiter._get_client_identifier(request)
        
        # Check per-minute limit
        minute_key = f"global_rate_limit:minute:{client_id}"
        minute_requests = cache.get(minute_key, 0)
        
        if minute_requests >= self.global_limits['requests_per_minute']:
            logger.warning(f"Global per-minute rate limit exceeded by {client_id}")
            return HttpResponse("Too many requests per minute", status=429)
        
        # Check per-hour limit
        hour_key = f"global_rate_limit:hour:{client_id}"
        hour_requests = cache.get(hour_key, 0)
        
        if hour_requests >= self.global_limits['requests_per_hour']:
            logger.warning(f"Global per-hour rate limit exceeded by {client_id}")
            return HttpResponse("Too many requests per hour", status=429)
        
        # Increment counters
        cache.set(minute_key, minute_requests + 1, timeout=60)
        cache.set(hour_key, hour_requests + 1, timeout=3600)
        
        response = self.get_response(request)
        
        # Add global rate limit headers
        response['X-RateLimit-Global-Minute-Limit'] = str(self.global_limits['requests_per_minute'])
        response['X-RateLimit-Global-Minute-Remaining'] = str(max(0, self.global_limits['requests_per_minute'] - minute_requests - 1))
        response['X-RateLimit-Global-Hour-Limit'] = str(self.global_limits['requests_per_hour'])
        response['X-RateLimit-Global-Hour-Remaining'] = str(max(0, self.global_limits['requests_per_hour'] - hour_requests - 1))
        
        return response


# Singleton instance
RATE_LIMITER = EnterpriseRateLimiter()