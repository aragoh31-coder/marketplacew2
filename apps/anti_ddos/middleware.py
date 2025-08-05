import logging
import hmac
import hashlib
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from core.utils.security import get_session_hash

logger = logging.getLogger(__name__)


class AntiDDoSMiddleware:
    """
    Session-based anti-DDoS middleware for Tor compatibility.
    Uses HMAC token verification instead of IP-based tracking.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return self.get_response(request)

        if self._is_internal_request(request):
            return self.get_response(request)

        if self._has_valid_token(request):
            return self.get_response(request)

        if request.path != reverse("anti_ddos:challenge"):
            return redirect(f"{reverse('anti_ddos:challenge')}?next={request.path}")

        return self.get_response(request)

    def _is_internal_request(self, request):
        """Check if request is from internal network"""
        remote_addr = request.META.get("REMOTE_ADDR", "")
        return (
            remote_addr.startswith("172.18.") or 
            remote_addr.startswith("127.0.0.1") or
            remote_addr == "localhost"
        )

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
