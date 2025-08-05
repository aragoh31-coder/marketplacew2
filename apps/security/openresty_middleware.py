import hashlib
import logging
import time

from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from core.utils.security import get_session_hash

logger = logging.getLogger("security")


class OpenRestyIntegrationMiddleware(MiddlewareMixin):

    def process_request(self, request):
        openresty_filtered = request.META.get("HTTP_X_OPENRESTY_FILTERED")
        pow_verified = request.META.get("HTTP_X_POW_VERIFIED")
        client_fingerprint = request.META.get("HTTP_X_CLIENT_FINGERPRINT")
        client_id = get_session_hash(request)

        remote_addr = request.META.get("REMOTE_ADDR", "")
        if (
            remote_addr.startswith("172.18.")
            or remote_addr.startswith("127.")
            or remote_addr == "localhost"
        ):
            logger.info(f"Internal network request from {remote_addr} - allowing")
            return None

        if not openresty_filtered and not self._is_health_check(request):
            logger.warning(
                f"Direct access attempt bypassing OpenResty from session {client_id}"
            )
            return HttpResponse(
                "Access denied - requests must go through security layer", status=403
            )

        if pow_verified:
            logger.info(f"PoW verified request from session {client_id}")
            request.META["POW_VERIFIED"] = True
            cache.set(f"pow_verified:{client_fingerprint}", True, 3600)

        if client_fingerprint:
            request.META["CLIENT_FINGERPRINT"] = client_fingerprint
            self._track_request_metrics(client_fingerprint, request)

        return None

    def _is_health_check(self, request):
        health_paths = ["/health", "/openresty-status", "/pow-challenge", "/pow-verify"]
        return any(request.path.startswith(path) for path in health_paths)

    def _track_request_metrics(self, fingerprint, request):
        current_time = int(time.time())
        minute_key = f"openresty_django_requests:{fingerprint}:{current_time // 60}"

        current_count = cache.get(minute_key, 0)
        cache.set(minute_key, current_count + 1, 60)

        if current_count > 15:
            logger.warning(
                f"High request rate from fingerprint {fingerprint}: {current_count + 1}/minute"
            )


    def process_response(self, request, response):
        response["X-Protected-By"] = "OpenResty-AntiDDoS + Django-Security"
        response["X-Security-Layers"] = "7"

        if hasattr(request, "META") and request.META.get("POW_VERIFIED"):
            response["X-PoW-Status"] = "Verified"

        return response
