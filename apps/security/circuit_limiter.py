import hashlib
import time

from django.core.cache import cache
from django.http import HttpResponse


class TorCircuitLimiter:
    """Rate limit based on Tor circuit fingerprints"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/anti_ddos/"):
            return self.get_response(request)

        circuit_id = self.get_circuit_fingerprint(request)

        if self.is_circuit_abusing(circuit_id):
            return HttpResponse("Circuit rate exceeded", status=429)

        response = self.get_response(request)
        return response

    def get_circuit_fingerprint(self, request):
        """Create unique fingerprint for Tor circuit"""
        factors = [
            request.META.get("HTTP_X_FORWARDED_FOR", ""),
            request.META.get("HTTP_USER_AGENT", ""),
            request.META.get("HTTP_ACCEPT_LANGUAGE", ""),
            request.META.get("HTTP_ACCEPT_ENCODING", ""),
        ]

        fingerprint_data = "|".join(factors)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    def is_circuit_abusing(self, circuit_id):
        """Check if circuit is making too many requests"""
        current_time = time.time()
        cache_key = f"circuit_limit:{circuit_id}"

        circuit_data = cache.get(cache_key, {"count": 0, "window_start": current_time})

        if current_time - circuit_data["window_start"] > 300:
            circuit_data = {"count": 0, "window_start": current_time}

        circuit_data["count"] += 1

        if circuit_data["count"] > 100:  # 100 requests per 5 minutes per circuit
            cache.set(cache_key, circuit_data, 300)
            return True

        cache.set(cache_key, circuit_data, 300)
        return False
