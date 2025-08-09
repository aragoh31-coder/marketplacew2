import logging
from django.shortcuts import redirect, render
from django.urls import reverse
from django.core.cache import cache
from core.utils.security import get_session_hash
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AntiDDoSMiddleware:
    """
    No-JS Tor-friendly anti-DDoS flow:
    Spinner → PoW → Captcha. Verification stored in cache per session/circuit.
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
            '/anti_ddos/spinner/',
            '/anti_ddos/status/',
            '/anti_ddos/challenge/',
            '/anti_ddos/pow/',
            '/anti_ddos/captcha/',
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

        if self._is_verified(request):
            return self.get_response(request)

        if request.path != reverse("anti_ddos:spinner"):
            return redirect(f"{reverse('anti_ddos:spinner')}?next={request.path}")

        return self.get_response(request)

    def _is_internal_request(self, request):
        return False

    def _is_verified(self, request):
        key = f"antiddos:verified:{get_session_hash(request)}"
        return bool(cache.get(key))

    def _render_blocked_page(self, request):
        return render(request, 'anti_ddos/blocked.html', {
            'reason': 'Your access has been temporarily restricted due to suspicious activity.'
        }, status=429)

    def _render_rate_limited_page(self, request):
        remaining = self.rate_limiter.get_remaining_requests(request)
        return render(request, 'anti_ddos/rate_limited.html', {
            'remaining_requests': remaining,
            'retry_after': 300
        }, status=429)
