from django import template
from django.core.cache import cache

register = template.Library()


@register.simple_tag
def is_2fa_verified(user, session_key):
    """Check if user has recently verified 2FA"""
    if not user.is_authenticated:
        return False
    cache_key = f"2fa_verified:{user.id}:{session_key}"
    return cache.get(cache_key, False)


@register.simple_tag
def requires_2fa_for_amount(amount, threshold=100):
    """Check if amount requires 2FA verification"""
    try:
        return float(amount) >= threshold
    except (ValueError, TypeError):
        return False


@register.filter
def has_2fa_enabled(user):
    """Check if user has any 2FA method enabled"""
    if not user.is_authenticated:
        return False
    return getattr(user, 'totp_enabled', False) or bool(getattr(user, 'pgp_public_key', ''))
