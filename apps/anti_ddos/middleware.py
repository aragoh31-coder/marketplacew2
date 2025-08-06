import logging
import hmac
import hashlib
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse
from core.utils.security import get_session_hash
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AntiDDoSMiddleware:
    """
    Session-based anti-DDoS middleware for Tor compatibility.
    Uses HMAC token verification and math challenges for protection.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limiter = RateLimiter()
        self.exempt_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/robots.txt',
        ]

    def __call__(self, request):
        for path in self.exempt_paths:
            if request.path.startswith(path):
                return self.get_response(request)

        if self._is_internal_request(request):
            return self.get_response(request)

        if self.rate_limiter.is_blocked(request):
            return self._render_blocked_page(request)

        if self.rate_limiter.is_rate_limited(request, 'global'):
            logger.warning(f"Rate limit exceeded for {self.rate_limiter.get_client_id(request)}")
            return self._render_rate_limited_page(request)

        if self._has_valid_token(request):
            return self.get_response(request)

        if request.path == reverse("anti_ddos:challenge") and request.method == 'POST':
            return self._handle_challenge_submission(request)

        if request.path != reverse("anti_ddos:challenge"):
            return redirect(f"{reverse('anti_ddos:challenge')}?next={request.path}")

        return self.get_response(request)

    def _is_internal_request(self, request):
        """Check if request is from internal network"""
        remote_addr = request.META.get("REMOTE_ADDR", "")
        return False

    def _has_valid_token(self, request):
        """Verify HMAC token from cookie"""
        token = request.COOKIES.get('ad_token')
        if not token:
            return False

        try:
            session_hash = get_session_hash(request)
            expected_data = f"verified|{session_hash}".encode()
            expected_token = hmac.new(
                settings.SECRET_KEY.encode(), 
                expected_data, 
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(token, expected_token)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return False

    def _handle_challenge_submission(self, request):
        """Handle math challenge submission"""
        if self.rate_limiter.is_rate_limited(request, 'challenge'):
            return self._render_rate_limited_page(request)

        return self.get_response(request)

    def _verify_math_challenge(self, request):
        """Verify math challenge answer"""
        try:
            submitted_answer = request.POST.get('math_answer', '').strip()
            correct_answer = request.session.get('math_answer')
            
            if not correct_answer or not submitted_answer:
                return False
            
            return int(submitted_answer) == int(correct_answer)
        except (ValueError, TypeError):
            return False

    def _render_blocked_page(self, request):
        """Render blocked page for temporarily blocked clients"""
        return render(request, 'anti_ddos/blocked.html', {
            'reason': 'Your access has been temporarily restricted due to suspicious activity.'
        }, status=429)

    def _render_rate_limited_page(self, request):
        """Render rate limited page"""
        remaining = self.rate_limiter.get_remaining_requests(request)
        return render(request, 'anti_ddos/rate_limited.html', {
            'remaining_requests': remaining,
            'retry_after': 300  # 5 minutes
        }, status=429)
