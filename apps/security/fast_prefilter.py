import time
from ipaddress import ip_address

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden


class FastPreFilterMiddleware:
    """
    In‐memory rate limiter that:
      • Exempts all private (RFC1918) & loopback IPs
      • Applies 50 req/min + burst-20 to everyone else
      • Permanently blocks offenders until restart
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.blocked_ips = set()  # IPs kicked out until restart
        self.request_log = {}  # ip → [timestamp, …]

        lim = getattr(settings, "FAST_PREFILTER_RATE_LIMIT", {})
        self.per_min = lim.get("per_minute", 50)
        self.burst = lim.get("burst", 20)

    def __call__(self, request):
        ip = request.META.get("REMOTE_ADDR")
        if ip:
            try:
                client = ip_address(ip)
                if client.is_private or client.is_loopback:
                    return self.get_response(request)
            except ValueError:
                pass

            if ip in self.blocked_ips:
                return HttpResponseForbidden("IP temporarily blocked")

            now = time.time()
            window = now - 60
            ts = [t for t in self.request_log.get(ip, []) if t >= window]
            ts.append(now)
            self.request_log[ip] = ts

            if len(ts) > self.per_min + self.burst:
                self.blocked_ips.add(ip)
                return HttpResponse("Rate limit exceeded", status=429)

        return self.get_response(request)
