import hashlib
import hmac
import time

import os
SECRET = os.environ.get('CIRCUIT_FINGERPRINT_SECRET', 'fallback-secret-change-in-production').encode()


def get_session_hash(request):
    """Generate a 16-char hash based on the session key."""
    if not request.session.session_key:
        request.session.create()
    key = request.session.session_key.encode('utf-8')
    return hashlib.sha256(key).hexdigest()[:16]


def circuit_fingerprint(user_agent: str) -> str:
    """
    Generate a circuit fingerprint based on user agent and time window.
    This creates a semi-persistent identifier for rate limiting that changes
    every 5 minutes to prevent long-term tracking while allowing short-term
    rate limiting for Tor users.
    """
    ts = str(int(time.time() // 300))  # 5-minute time windows
    raw = f"{user_agent}|{ts}"
    return hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()


def validate_crypto_address(address: str) -> bool:
    """
    Validate cryptocurrency addresses for BTC and XMR.
    """
    import re

    btc_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$"
    xmr_pattern = r"^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$"
    return bool(re.match(btc_pattern, address)) or bool(re.match(xmr_pattern, address))
