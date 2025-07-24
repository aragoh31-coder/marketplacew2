import time
import hashlib
import json
import re
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('wallet.security')


class WalletSecurityMiddleware(MiddlewareMixin):
    """Enhanced wallet security middleware with comprehensive protection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return None
        
        if self._is_advanced_bot(request):
            return self._handle_bot_detection(request)
        
        if not self._check_ip_consistency(request):
            return self._handle_ip_inconsistency(request)
        
        if not self._check_session_timeout(request):
            return self._handle_session_timeout(request)
        
        if not self._check_multi_window_rate_limit(request):
            return self._handle_rate_limit(request)
        
        return None
    
    def process_response(self, request, response):
        return self._add_security_headers(response)
    
    def _is_advanced_bot(self, request):
        """Advanced bot detection with multiple signals"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        bot_patterns = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'scrapy', 'selenium', 'phantomjs',
            'headless', 'automation', 'test'
        ]
        
        for pattern in bot_patterns:
            if pattern in user_agent:
                return True
        
        essential_headers = ['HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING']
        missing_headers = sum(1 for header in essential_headers if not request.META.get(header))
        
        if missing_headers >= 2:
            return True
        
        accept = request.META.get('HTTP_ACCEPT', '')
        if accept and 'text/html' not in accept and request.method == 'GET':
            return True
        
        return False
    
    def _check_ip_consistency(self, request):
        """Check IP address consistency for authenticated users"""
        if not request.user.is_authenticated:
            return True
        
        current_ip = self._get_client_ip(request)
        session_ip = request.session.get('login_ip')
        
        if session_ip and session_ip != current_ip:
            logger.warning(f"IP change detected for user {request.user.username}")
            return False
        
        if not session_ip:
            request.session['login_ip'] = current_ip
        
        return True
    
    def _check_session_timeout(self, request):
        """Enhanced session timeout with activity tracking"""
        if not request.user.is_authenticated:
            return True
        
        last_activity = request.session.get('last_activity')
        if last_activity:
            inactive_time = timezone.now().timestamp() - last_activity
            
            if request.path.startswith('/wallets/'):
                timeout = 900  # 15 minutes for wallet operations
            elif request.path.startswith('/adminpanel/'):
                timeout = 600  # 10 minutes for admin
            else:
                timeout = 1800  # 30 minutes for general
            
            if inactive_time > timeout:
                request.session.flush()
                return False
        
        request.session['last_activity'] = timezone.now().timestamp()
        return True
    
    def _check_multi_window_rate_limit(self, request):
        """Multi-window rate limiting with different limits"""
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        limits = [
            ('1min', 60, 20),    # 20 requests per minute
            ('5min', 300, 50),   # 50 requests per 5 minutes
            ('1hour', 3600, 200) # 200 requests per hour
        ]
        
        for window_name, window_size, limit in limits:
            cache_key = f"rate_limit:{window_name}:{ip}"
            requests = cache.get(cache_key, [])
            
            requests = [req_time for req_time in requests if current_time - req_time < window_size]
            
            if len(requests) >= limit:
                return False
            
            requests.append(current_time)
            cache.set(cache_key, requests, window_size)
        
        return True
    
    def _get_client_ip(self, request):
        """Get client IP with proxy support"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def _handle_bot_detection(self, request):
        """Handle detected bots"""
        return render(request, 'security/bot_detected.html', status=403)
    
    def _handle_ip_inconsistency(self, request):
        """Handle IP address changes"""
        request.session.flush()
        return redirect('accounts:login')
    
    def _handle_session_timeout(self, request):
        """Handle session timeout"""
        return redirect('accounts:login')
    
    def _handle_rate_limit(self, request):
        """Handle rate limit exceeded"""
        return render(request, 'security/rate_limited.html', status=429)
    
    def _add_security_headers(self, response):
        """Add comprehensive security headers"""
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': "default-src 'self'; script-src 'none'; object-src 'none'; style-src 'self' 'unsafe-inline';",
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
        }
        
        for header, value in security_headers.items():
            response[header] = value
        
        return response


class RateLimitMiddleware:
    """Rate limiting middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            
            if '/withdraw/' in path:
                if not self.check_rate_limit(
                    request, 
                    'withdraw',
                    settings.WALLET_SECURITY.get('WITHDRAWAL_RATE_LIMIT', 5)
                ):
                    messages.error(
                        request,
                        "Too many withdrawal attempts. Please try again later."
                    )
                    return redirect('wallets:dashboard')
            
            elif '/convert/' in path:
                if not self.check_rate_limit(
                    request,
                    'convert',
                    settings.WALLET_SECURITY.get('CONVERSION_RATE_LIMIT', 20)
                ):
                    messages.error(
                        request,
                        "Too many conversion attempts. Please try again later."
                    )
                    return redirect('wallets:dashboard')
        
        response = self.get_response(request)
        return response
    
    def check_rate_limit(self, request, action, max_attempts):
        """Check rate limit for specific action"""
        ip = self.get_client_ip(request)
        cache_key = f'rate_limit:{action}:{ip}:{request.user.id}'
        
        attempts = cache.get(cache_key, 0)
        if attempts >= max_attempts:
            logger.warning(
                f"Rate limit exceeded for {action} by user {request.user.username} "
                f"from IP {ip}"
            )
            return False
        
        cache.set(cache_key, attempts + 1, 3600)
        return True
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class EnhancedSecurityMiddleware:
    """Enhanced security middleware with comprehensive bot detection"""
    
    BOT_USER_AGENTS = [
        r'.*bot.*', r'.*crawler.*', r'.*spider.*', r'.*scraper.*',
        r'curl', r'wget', r'python-requests', r'http', r'test',
        r'automated', r'headless', r'phantom', r'selenium', r'webdriver'
    ]
    
    SUSPICIOUS_PATTERNS = [
        r'/admin', r'/wp-admin', r'\.php$', r'\.asp$',
        r'/config', r'/backup', r'\.sql$', r'\.env$',
        r'/\.git', r'/\.svn', r'/\.htaccess'
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_bot_request(request):
            logger.warning(f"Bot detected: {request.META.get('HTTP_USER_AGENT', '')}")
            return render(request, 'security/bot_challenge.html', {
                'challenge_question': 'What is 2 + 2?',
                'challenge_id': 'bot_challenge',
                'timestamp': time.time(),
                'expected_answer': 4
            })
        
        if self._is_suspicious_request(request):
            logger.warning(f"Suspicious request: {request.path}")
            return HttpResponseForbidden("Access denied")
        
        if self._is_rate_limited(request):
            return render(request, 'security/rate_limited.html', {
                'retry_after': 60
            })
        
        response = self.get_response(request)
        
        self._add_security_headers(response)
        
        return response

    def _is_bot_request(self, request):
        """Enhanced bot detection"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        for pattern in self.BOT_USER_AGENTS:
            if re.search(pattern, user_agent, re.IGNORECASE):
                if any(legit in user_agent for legit in ['googlebot', 'bingbot', 'duckduckbot']):
                    return False
                return True
        
        if not user_agent or len(user_agent) < 10:
            return True
        
        if not request.META.get('HTTP_ACCEPT_LANGUAGE'):
            return True
        
        return False

    def _is_suspicious_request(self, request):
        """Check for suspicious request patterns"""
        path = request.path.lower()
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, path):
                return True
        
        for key, value in request.GET.items():
            if any(sql_keyword in str(value).lower() for sql_keyword in 
                   ['union', 'select', 'drop', 'insert', 'delete', 'update', 'exec']):
                return True
        
        for key, value in request.GET.items():
            if any(xss_pattern in str(value).lower() for xss_pattern in 
                   ['<script', 'javascript:', 'onload=', 'onerror=', 'eval(']):
                return True
        
        return False

    def _is_rate_limited(self, request):
        """Advanced rate limiting"""
        ip_hash = hashlib.sha256(
            self.get_client_ip(request).encode()
        ).hexdigest()
        
        windows = [
            ('1min', 60, 30),    # 30 requests per minute
            ('5min', 300, 100),  # 100 requests per 5 minutes
            ('1hour', 3600, 500) # 500 requests per hour
        ]
        
        for window_name, duration, limit in windows:
            cache_key = f"rate_limit_{window_name}_{ip_hash}"
            request_count = cache.get(cache_key, 0)
            
            if request_count >= limit:
                logger.warning(f"Rate limit exceeded: {window_name} for {ip_hash}")
                return True
            
            cache.set(cache_key, request_count + 1, duration)
        
        return False

    def _add_security_headers(self, response):
        """Add comprehensive security headers"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; object-src 'none'; style-src 'self' 'unsafe-inline';"
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
