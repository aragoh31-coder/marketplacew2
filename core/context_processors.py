from django.conf import settings


def marketplace_context(request):
    """Add marketplace-specific context variables"""
    context = {
        'marketplace_name': 'Tor Marketplace',
        'marketplace_version': '2.0',
        'debug_mode': settings.DEBUG,
        'tor_only': True,
        'security_features': {
            'anti_ddos': True,
            'two_factor_auth': True,
            'pgp_encryption': True,
            'tor_only': True,
        }
    }
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        from django.core.cache import cache
        cache_key = f"2fa_verified:{request.user.id}:{request.session.session_key}"
        context['user_2fa_verified'] = cache.get(cache_key, False)
    
    return context
