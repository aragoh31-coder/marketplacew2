from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
import hashlib
import logging
import re

logger = logging.getLogger('security.bot_detection')


class BotDetectionMiddleware:
    """Advanced bot detection and rate limiting middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        self.bot_user_agents = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'python-requests', r'scrapy', r'selenium', r'phantomjs'
        ]
        
        self.suspicious_paths = [
            r'/wp-admin/', r'/admin\.php', r'\.php$', r'\.asp$',
            r'/xmlrpc\.php', r'/wp-login\.php', r'/phpmyadmin/'
        ]
        
        self.rate_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'login_attempts_per_hour': 10,
            'registration_attempts_per_hour': 5
        }
    
    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)
        
        client_id = self.get_client_identifier(request)
        
        if self.is_blocked(client_id):
            logger.warning(f"Blocked request from {client_id}")
            return HttpResponseForbidden("Access denied")
        
        if self.detect_bot_patterns(request):
            self.flag_suspicious_activity(client_id, 'bot_pattern')
            logger.warning(f"Bot pattern detected from {client_id}")
            return HttpResponseForbidden("Access denied")
        
        if not self.check_rate_limits(request, client_id):
            self.flag_suspicious_activity(client_id, 'rate_limit_exceeded')
            logger.warning(f"Rate limit exceeded for {client_id}")
            return render(request, 'security/rate_limited.html', status=429)
        
        response = self.get_response(request)
        
        self.track_request(request, client_id)
        
        return response
    
    def get_client_identifier(self, request):
        """Get anonymized client identifier for privacy"""
        ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        identifier = hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()[:16]
        return identifier
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def is_blocked(self, client_id):
        """Check if client is blocked"""
        return cache.get(f"blocked:{client_id}", False)
    
    def detect_bot_patterns(self, request):
        """Detect bot-like behavior patterns"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path.lower()
        
        for pattern in self.bot_user_agents:
            if re.search(pattern, user_agent):
                return True
        
        for pattern in self.suspicious_paths:
            if re.search(pattern, path):
                return True
        
        if not request.META.get('HTTP_ACCEPT'):
            return True
        
        if 'python' in user_agent and not request.META.get('HTTP_ACCEPT_LANGUAGE'):
            return True
        
        return False
    
    def check_rate_limits(self, request, client_id):
        """Check various rate limits"""
        current_time = timezone.now()
        
        minute_key = f"requests_minute:{client_id}:{current_time.strftime('%Y%m%d%H%M')}"
        hour_key = f"requests_hour:{client_id}:{current_time.strftime('%Y%m%d%H')}"
        
        minute_count = cache.get(minute_key, 0)
        hour_count = cache.get(hour_key, 0)
        
        if minute_count >= self.rate_limits['requests_per_minute']:
            return False
        
        if hour_count >= self.rate_limits['requests_per_hour']:
            return False
        
        if '/accounts/login/' in request.path:
            login_key = f"login_attempts:{client_id}:{current_time.strftime('%Y%m%d%H')}"
            login_count = cache.get(login_key, 0)
            if login_count >= self.rate_limits['login_attempts_per_hour']:
                return False
        
        if '/accounts/register/' in request.path:
            reg_key = f"registration_attempts:{client_id}:{current_time.strftime('%Y%m%d%H')}"
            reg_count = cache.get(reg_key, 0)
            if reg_count >= self.rate_limits['registration_attempts_per_hour']:
                return False
        
        return True
    
    def track_request(self, request, client_id):
        """Track request for rate limiting"""
        current_time = timezone.now()
        
        minute_key = f"requests_minute:{client_id}:{current_time.strftime('%Y%m%d%H%M')}"
        hour_key = f"requests_hour:{client_id}:{current_time.strftime('%Y%m%d%H')}"
        
        cache.set(minute_key, cache.get(minute_key, 0) + 1, 60)
        cache.set(hour_key, cache.get(hour_key, 0) + 1, 3600)
        
        if '/accounts/login/' in request.path and request.method == 'POST':
            login_key = f"login_attempts:{client_id}:{current_time.strftime('%Y%m%d%H')}"
            cache.set(login_key, cache.get(login_key, 0) + 1, 3600)
        
        if '/accounts/register/' in request.path and request.method == 'POST':
            reg_key = f"registration_attempts:{client_id}:{current_time.strftime('%Y%m%d%H')}"
            cache.set(reg_key, cache.get(reg_key, 0) + 1, 3600)
    
    def flag_suspicious_activity(self, client_id, reason):
        """Flag suspicious activity and potentially block"""
        flag_key = f"suspicious_flags:{client_id}"
        flags = cache.get(flag_key, [])
        
        flags.append({
            'reason': reason,
            'timestamp': timezone.now().isoformat()
        })
        
        cutoff = timezone.now() - timedelta(hours=1)
        flags = [f for f in flags if timezone.datetime.fromisoformat(f['timestamp']) > cutoff]
        
        cache.set(flag_key, flags, 3600)
        
        if len(flags) >= 5:
            cache.set(f"blocked:{client_id}", True, 3600)  # Block for 1 hour
            logger.error(f"Blocking client {client_id} due to suspicious activity: {flags}")


class SecurityHeadersMiddleware:
    """Add security headers to all responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'none'; "  # No JavaScript for Tor compatibility
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'none'; "
            "frame-src 'none'; "
            "object-src 'none'"
        )
        
        if 'Server' in response:
            del response['Server']
        
        return response


class BotDetector:
    """Standalone bot detection utility class"""
    
    def __init__(self):
        self.bot_patterns = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'python-requests', r'scrapy', r'selenium', r'phantomjs'
        ]
    
    def is_bot(self, user_agent):
        """Check if user agent indicates a bot"""
        if not user_agent:
            return True
        
        user_agent = user_agent.lower()
        
        for pattern in self.bot_patterns:
            if re.search(pattern, user_agent):
                return True
        
        return False
    
    def check_request_headers(self, request):
        """Check request headers for bot indicators"""
        if not request.META.get('HTTP_ACCEPT'):
            return True
        
        if not request.META.get('HTTP_ACCEPT_LANGUAGE'):
            return True
        
        return False
