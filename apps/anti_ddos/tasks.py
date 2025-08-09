import hashlib, random, string, time
from django.core.cache import cache

def _solve(prefix: str, timeout: int):
    deadline = time.time() + max(1, timeout)
    alphabet = string.ascii_letters + string.digits
    while time.time() < deadline:
        s = "".join(random.choices(alphabet, k=10))
        h = hashlib.sha256(s.encode()).hexdigest()
        if h.startswith(prefix):
            return s, h
    return None, None

try:
    from celery import shared_task
except Exception:
    def shared_task(*a, **k):
        def wrapper(fn): return fn
        return wrapper

@shared_task(rate_limit="2/s", soft_time_limit=15, time_limit=20)
def autosolve_pow(session_hash: str, prefix: str, ttl: int, timeout: int):
    key_verified = f"antiddos:verified:{session_hash}"
    if cache.get(key_verified):
        return {"ok": True, "already": True}
    sol, h = _solve(prefix, timeout)
    if sol:
        cache.set(key_verified, True, ttl)
        return {"ok": True, "solution": sol, "hash": h}
    return {"ok": False}
