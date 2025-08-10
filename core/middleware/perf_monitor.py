import logging
import time

perf_logger = logging.getLogger("perf")


class PerfMonitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        method = request.method
        path = request.path
        is_auth = False
        user = getattr(request, "user", None)
        if user is not None and hasattr(user, "is_authenticated"):
            is_auth = bool(user.is_authenticated)

        response = self.get_response(request)

        duration_ms = int((time.time() - start) * 1000)
        status = getattr(response, "status_code", 0)
        has_cookie = False
        try:
            for h, _v in response.items():
                if h.lower() == "set-cookie":
                    has_cookie = True
                    break
        except Exception:
            has_cookie = False

        try:
            perf_logger.info(
                "req method=%s path=%s status=%s ms=%s auth=%s set_cookie=%s",
                method,
                path,
                status,
                duration_ms,
                1 if is_auth else 0,
                1 if has_cookie else 0,
            )
        except Exception:
            pass

        return response
