import secrets
import time

from django.conf import settings
from django.utils import timezone


def security_context(request):
    """Provide security-related context variables to templates"""
    context = {
        "security_enabled": getattr(settings, "SECURITY_SETTINGS", {}).get(
            "ENABLE_BOT_DETECTION", True
        ),
        "captcha_enabled": getattr(settings, "SECURITY_SETTINGS", {}).get(
            "ENABLE_MATH_CAPTCHA", True
        ),
        "rate_limiting_enabled": getattr(settings, "SECURITY_SETTINGS", {}).get(
            "ENABLE_RATE_LIMITING", True
        ),
    }

    if hasattr(request, "user") and request.user.is_authenticated:
        context.update(
            {
                "user_security_score": calculate_user_security_score(request.user),
                "has_2fa": hasattr(request.user, "totp_enabled")
                and request.user.totp_enabled,
                "has_pgp": bool(getattr(request.user, "pgp_public_key", "")),
            }
        )

    return context


def calculate_user_security_score(user):
    """Calculate basic security score for user"""
    score = 50  # Base score

    if hasattr(user, "totp_enabled") and user.totp_enabled:
        score += 20

    if getattr(user, "pgp_public_key", ""):
        score += 15

    account_age = (timezone.now().date() - user.date_joined.date()).days
    if account_age >= 90:
        score += 15
    elif account_age >= 30:
        score += 10
    elif account_age >= 7:
        score += 5

    return max(0, min(100, score))


def captcha_data(request):
    """Add CAPTCHA-related context data"""
    return {
        'captcha_enabled': True,
        'captcha_timeout': 300,
    }
