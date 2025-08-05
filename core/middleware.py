import logging

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger(__name__)


def is_tor_request(request):
    """Check if request is coming through Tor"""
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    if "tor" in user_agent:
        return True

    host = request.META.get("HTTP_HOST", "")
    if ".onion" in host:
        return True

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return True

    return False


def get_tor_status(request):
    if not hasattr(request, "_tor_status"):
        request._tor_status = is_tor_request(request)
    return request._tor_status


class TorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tor_session = SimpleLazyObject(lambda: get_tor_status(request))
        response = self.get_response(request)
        return response


class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


try:
    import redis

    from .utils.security import circuit_fingerprint

    r = redis.StrictRedis(host="redis", port=6379, db=0, decode_responses=True)
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

        if request.path.startswith("/anti_ddos/"):
            return self.get_response(request)

        fingerprint = circuit_fingerprint(
            request.META.get("HTTP_USER_AGENT", "unknown")
        )
        key = f"rl:{fingerprint}"

        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            if count > 20:
                return HttpResponseForbidden(
                    "Too many requests. Please wait before trying again."
                )
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

        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'none'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'none'; "
            "frame-src 'none'; "
            "object-src 'none';"
        )

        response["Referrer-Policy"] = "no-referrer"
        response["X-Frame-Options"] = "DENY"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response
