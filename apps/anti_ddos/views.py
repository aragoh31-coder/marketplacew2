import hashlib, hmac, time, secrets, random
from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.core.cache import cache
from django.utils.crypto import constant_time_compare
from core.utils.security import get_session_hash
from .tasks import autosolve_pow

import logging
perf_logger = logging.getLogger("perf")
PREFIX = getattr(settings, "ANTIDDOS", {}).get("POW_PREFIX", "0000")
TTL = getattr(settings, "ANTIDDOS", {}).get("TTL", 900)
AUTO = getattr(settings, "ANTIDDOS", {}).get("AUTO_POW", True)
AUTO_TIMEOUT = getattr(settings, "ANTIDDOS", {}).get("AUTO_POW_TIMEOUT", 8)
MAX_REFRESH = getattr(settings, "ANTIDDOS", {}).get("AUTO_POW_MAX_REFRESH", 6)

def _issue_token(request):
    session_hash = get_session_hash(request)
    ts = str(int(time.time()))
    msg = f"{session_hash}:{ts}".encode()
    token = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
    cache.set(f"antiddos:{session_hash}:ts", ts, TTL)
    return token, session_hash, ts

def _verified(session_hash):
    return bool(cache.get(f"antiddos:verified:{session_hash}"))

def _client_id(request):
    fp = request.META.get("HTTP_X_CLIENT_FINGERPRINT")
    if fp:
        return fp
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    base = f"{ip}:{ua}".encode()
    return hashlib.sha256(base).hexdigest()[:16]

@ensure_csrf_cookie
def spinner(request):
    token, session_hash, ts = _issue_token(request)
    if AUTO:
        qkey = f"antiddos:autoq:{session_hash}"
        if not cache.get(qkey):
            autosolve_pow.delay(session_hash, PREFIX, TTL, AUTO_TIMEOUT)
            cache.set(qkey, True, 60)
        resp = redirect("anti_ddos:status")
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "1" if _verified(session_hash) else "0"
        return resp
    resp = render(request, "anti_ddos/spinner.html", {"session_hash": session_hash, "token": token, "ts": ts})
    resp["X-AD-Session"] = session_hash
    resp["X-AD-Verified"] = "1" if _verified(session_hash) else "0"
    return resp

def status(request):
    session_hash = get_session_hash(request)
    if _verified(session_hash):
        resp = redirect("/")
        try:
            resp.set_cookie("hmac_token", "ok", max_age=TTL, samesite="Strict", path="/")
        except Exception:
            pass
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "1"
        return resp
    k = f"antiddos:polls:{session_hash}"
    polls = int(cache.get(k, 0)) + 1
    cache.set(k, polls, 120)
    cid = _client_id(request)
    kc = f"antiddos:polls_cid:{cid}"
    cid_polls = int(cache.get(kc, 0)) + 1
    cache.set(kc, cid_polls, 120)
    if polls >= MAX_REFRESH or cid_polls >= MAX_REFRESH:
        resp = redirect("anti_ddos:pow")
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "0"
        resp["X-AD-Polls"] = str(polls)
        resp["X-AD-CID"] = cid
        resp["X-AD-CID-Polls"] = str(cid_polls)
        return resp
    resp = render(request, "anti_ddos/status.html", {"refresh_seconds": 2})
    resp["X-AD-Session"] = session_hash
    resp["X-AD-Verified"] = "0"
    resp["X-AD-Polls"] = str(polls)
    resp["X-AD-CID"] = cid
    resp["X-AD-CID-Polls"] = str(cid_polls)
    return resp

@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def pow_challenge(request):
    if request.method == "GET":
        token, session_hash, ts = _issue_token(request)
        prefix = PREFIX
        cache.set(f"antiddos:{session_hash}:prefix", prefix, TTL)
        resp = render(request, "anti_ddos/pow_form.html", {"prefix": prefix, "token": token})
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "1" if _verified(session_hash) else "0"
        return resp

    solution = (request.POST.get("solution") or "").strip()
    prefix = (request.POST.get("prefix") or "").strip()
    session_hash = get_session_hash(request)
    ts = cache.get(f"antiddos:{session_hash}:ts") or ""
    token = (request.POST.get("token") or "").strip()
    expected = hmac.new(settings.SECRET_KEY.encode(), f"{session_hash}:{ts}".encode(), hashlib.sha256).hexdigest()

    if not (constant_time_compare(token, expected) and prefix and solution):
        resp = redirect("anti_ddos:spinner")
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "0"
        return resp

    if hashlib.sha256(solution.encode()).hexdigest().startswith(prefix):
        cache.set(f"antiddos:verified:{session_hash}", True, TTL)
        resp = redirect("/")
        try:
            resp.set_cookie("hmac_token", "ok", max_age=TTL, samesite="Strict", path="/")
        except Exception:
            pass
        resp["X-AD-Session"] = session_hash
        resp["X-AD-Verified"] = "1"
        return resp
    resp = redirect("anti_ddos:captcha")
    resp["X-AD-Session"] = session_hash
    resp["X-AD-Verified"] = "0"
    return resp

@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def captcha(request):
    session_hash = get_session_hash(request)
    cache_key = f"antiddos:captcha:{session_hash}"

    if request.method == "GET":
        a, b = random.randint(1, 20), random.randint(1, 20)
        challenge = {
            "id": secrets.token_hex(8),
            "text": f"{a} + {b}",
            "answer": str(a + b),
        }
        cache.set(cache_key, challenge, TTL)
        resp = render(request, "anti_ddos/captcha.html", {
            "challenge_id": challenge["id"],
            "challenge_text": challenge["text"],
        })
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        resp["X-AntiDDoS-Trace"] = challenge["id"]
        return resp

    challenge = cache.get(cache_key)
    if not isinstance(challenge, dict) or "answer" not in challenge or "text" not in challenge:
        a, b = random.randint(1, 20), random.randint(1, 20)
        challenge = {
            "id": secrets.token_hex(8),
            "text": f"{a} + {b}",
            "answer": str(a + b),
        }
        cache.set(cache_key, challenge, TTL)
        resp = render(request, "anti_ddos/captcha.html", {
            "challenge_id": challenge["id"],
            "challenge_text": challenge["text"],
            "error": "Challenge refreshed. Please solve the new problem.",
        })
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        resp["X-AntiDDoS-Trace"] = challenge["id"]
        return resp

    user_answer = (request.POST.get("answer") or "").strip()
    if constant_time_compare(user_answer, challenge["answer"]):
        cache.set(f"antiddos:verified:{session_hash}", True, TTL)
        try:
            perf_logger.info("antiddos_verified ttl=%s", TTL)
        except Exception:
            pass
        resp = redirect("/")
        try:
            resp.set_cookie("hmac_token", "ok", max_age=TTL, samesite="Strict", path="/")
        except Exception:
            pass
        resp.set_cookie("antiddos_ok", "1", max_age=TTL, httponly=True, samesite="Strict", secure=True, path="/")
        return resp

    resp = render(request, "anti_ddos/captcha.html", {
        "challenge_id": challenge["id"],
        "challenge_text": challenge["text"],
        "error": "Incorrect answer. Try again.",
    })
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["X-AntiDDoS-Trace"] = challenge["id"]
    return resp
@ensure_csrf_cookie
@require_http_methods(["GET", "HEAD"])
def challenge(request):
    return render(request, "anti_ddos/challenge.html")
