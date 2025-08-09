from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def marketplace_setting(setting_name, default=None):
    """Get marketplace setting value"""
    return getattr(settings, setting_name, default)


@register.filter
def format_currency(amount, currency='USD'):
    """Format currency amount"""
    try:
        amount = float(amount)
        if currency == 'USD':
            return f"${amount:.2f}"
        elif currency == 'BTC':
            return f"{amount:.8f} BTC"
        elif currency == 'XMR':
            return f"{amount:.12f} XMR"
        return f"{amount} {currency}"
    except (ValueError, TypeError):
        return f"0 {currency}"


@register.inclusion_tag('partials/2fa_status.html')
def show_2fa_status(user):
    """Show user's 2FA status"""
    return {
        'user': user,
        'totp_enabled': getattr(user, 'totp_enabled', False),
        'pgp_enabled': bool(getattr(user, 'pgp_public_key', '')),
    }
