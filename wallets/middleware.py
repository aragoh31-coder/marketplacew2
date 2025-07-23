from django.core.cache import cache
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
import hashlib
import logging

logger = logging.getLogger('wallet.security')


class WalletSecurityMiddleware:
    """Enhanced security middleware for wallet operations with Tor compatibility"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            self.check_session_timeout(request)
            
            request.session['last_activity'] = timezone.now().timestamp()
        
        response = self.get_response(request)
        
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['X-Frame-Options'] = 'DENY'
        
        return response
    
    def check_session_timeout(self, request):
        """Check for session timeout"""
        last_activity = request.session.get('last_activity')
        if last_activity:
            timeout_minutes = getattr(settings, 'WALLET_SESSION_TIMEOUT_MINUTES', 30)
            if timezone.now().timestamp() - last_activity > (timeout_minutes * 60):
                from django.contrib.auth import logout
                logout(request)
                messages.info(
                    request, 
                    "Your session has expired due to inactivity."
                )
    
    def get_anonymized_ip(self, request):
        """Get anonymized IP address for privacy protection"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return hashlib.sha256(ip.encode()).hexdigest()[:16]


class RateLimitMiddleware:
    """Enhanced rate limiting middleware with Tor compatibility"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            
            if '/wallets/withdraw/' in path and request.method == 'POST':
                if not self.check_rate_limit(request, 'withdraw', 5, 3600):
                    messages.error(request, "Too many withdrawal attempts. Please try again later.")
                    return redirect('wallets:dashboard')
            
            elif '/wallets/convert/' in path and request.method == 'POST':
                if not self.check_rate_limit(request, 'convert', 20, 3600):
                    messages.error(request, "Too many conversion attempts. Please try again later.")
                    return redirect('wallets:dashboard')
            
            elif '/wallets/security/' in path and request.method == 'POST':
                if not self.check_rate_limit(request, 'security_change', 10, 3600):
                    messages.error(request, "Too many security changes. Please try again later.")
                    return redirect('wallets:dashboard')
        
        return self.get_response(request)
    
    def check_rate_limit(self, request, action, max_attempts, window):
        """Check rate limit for specific action with anonymized tracking"""
        anonymized_ip = self.get_anonymized_ip(request)
        cache_key = f'rate_limit:{action}:{request.user.id}:{anonymized_ip}'
        
        attempts = cache.get(cache_key, 0)
        if attempts >= max_attempts:
            logger.warning(
                f"Rate limit exceeded for {action} by user {request.user.username}"
            )
            return False
        
        cache.set(cache_key, attempts + 1, window)
        return True
    
    def get_anonymized_ip(self, request):
        """Get anonymized IP address for privacy protection"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
