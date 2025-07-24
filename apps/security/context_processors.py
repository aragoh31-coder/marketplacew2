from django.conf import settings
from django.utils import timezone
import secrets
import time


def security_context(request):
    """Provide security-related context variables to templates"""
    context = {
        'security_enabled': getattr(settings, 'SECURITY_SETTINGS', {}).get('ENABLE_BOT_DETECTION', True),
        'captcha_enabled': getattr(settings, 'SECURITY_SETTINGS', {}).get('ENABLE_MATH_CAPTCHA', True),
        'rate_limiting_enabled': getattr(settings, 'SECURITY_SETTINGS', {}).get('ENABLE_RATE_LIMITING', True),
    }
    
    if request.user.is_authenticated:
        context.update({
            'user_security_score': calculate_user_security_score(request.user),
            'has_2fa': hasattr(request.user, 'wallet') and getattr(request.user.wallet, 'two_fa_enabled', False),
            'has_pgp': bool(request.user.pgp_public_key),
        })
    
    return context


def calculate_user_security_score(user):
    """Calculate basic security score for user"""
    score = 50  # Base score
    
    if hasattr(user, 'wallet') and getattr(user.wallet, 'two_fa_enabled', False):
        score += 20
    
    if user.pgp_public_key:
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
    """Context processor for CAPTCHA data"""
    if not hasattr(request, '_captcha_data'):
        num1 = secrets.randbelow(10) + 1
        num2 = secrets.randbelow(10) + 1
        answer = num1 + num2
        
        timestamp = time.time()
        
        form_hash = secrets.token_urlsafe(16)
        
        request._captcha_data = {
            'math_challenge': f"{num1} + {num2}",
            'math_answer': answer,
            'form_timestamp': timestamp,
            'form_hash': form_hash,
        }
        
        request.session['captcha_answer'] = answer
        request.session['captcha_timestamp'] = timestamp
        request.session['captcha_hash'] = form_hash
    
    return {
        'captcha_data': request._captcha_data
    }
