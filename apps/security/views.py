from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from wallets.models import AuditLog
import random
import time
import hashlib


@login_required
def security_status(request):
    """Display user's security status and recent events"""
    user = request.user
    
    security_score = 0
    
    two_fa_enabled = hasattr(user, 'wallet') and user.wallet.two_fa_enabled
    if two_fa_enabled:
        security_score += 30
    
    pgp_key_set = bool(user.pgp_public_key)
    if pgp_key_set:
        security_score += 25
    
    account_age = (timezone.now().date() - user.date_joined.date()).days
    if account_age >= 90:
        security_score += 25
    elif account_age >= 30:
        security_score += 15
    elif account_age >= 7:
        security_score += 10
    
    if user.last_login:
        days_since_login = (timezone.now() - user.last_login).days
        if days_since_login <= 7:
            security_score += 20
        elif days_since_login <= 30:
            security_score += 10
    
    recent_events = AuditLog.objects.filter(
        user=user
    ).order_by('-created_at')[:20]
    
    security_info = {
        'security_score': min(security_score, 100),
        'two_fa_enabled': two_fa_enabled,
        'pgp_key_set': pgp_key_set,
        'account_age': account_age,
        'last_login': user.last_login,
    }
    
    return render(request, 'security/security_status.html', {
        'security_info': security_info,
        'recent_events': recent_events,
    })


def bot_challenge(request):
    """Handle bot challenge verification"""
    if request.method == 'POST':
        from apps.security.forms import BotChallengeForm
        
        expected_answer = request.session.get('bot_challenge_answer')
        
        form = BotChallengeForm(request.POST, expected_answer=expected_answer)
        
        if form.is_valid():
            request.session.pop('bot_challenge_answer', None)
            request.session.pop('bot_challenge_timestamp', None)
            
            request.session['bot_challenge_passed'] = True
            
            next_url = request.session.get('bot_challenge_next', '/')
            request.session.pop('bot_challenge_next', None)
            
            return redirect(next_url)
        else:
            messages.error(request, 'Challenge failed. Please try again.')
    
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(['+', '-', '*'])
    
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2}"
    elif operation == '-':
        answer = num1 - num2
        question = f"{num1} - {num2}"
    else:  # multiplication
        answer = num1 * num2
        question = f"{num1} × {num2}"
    
    request.session['bot_challenge_answer'] = answer
    request.session['bot_challenge_timestamp'] = time.time()
    
    form = BotChallengeForm(initial={
        'timestamp': time.time(),
        'challenge_id': f"challenge_{int(time.time())}"
    })
    
    return render(request, 'security/bot_challenge.html', {
        'form': form,
        'question': question,
        'challenge_id': f"challenge_{int(time.time())}"
    })


def captcha_challenge(request):
    """Handle CAPTCHA challenge"""
    if request.method == 'POST':
        user_answer = request.POST.get('captcha_answer', '').strip()
        expected_answer = request.session.get('captcha_answer', '')
        
        if request.POST.get('website') or request.POST.get('email_address'):
            messages.error(request, 'Bot detected. Access denied.')
            return redirect('security:captcha_challenge')
        
        if user_answer.lower() == expected_answer.lower():
            request.session['captcha_verified'] = True
            request.session.pop('captcha_answer', None)
            
            next_url = request.session.get('captcha_next', '/')
            request.session.pop('captcha_next', None)
            
            messages.success(request, 'Verification successful!')
            return redirect(next_url)
        else:
            messages.error(request, 'Incorrect CAPTCHA answer. Please try again.')
    
    words = ['SECURE', 'MARKET', 'CRYPTO', 'WALLET', 'TRADE', 'PRIVACY', 'SAFETY']
    captcha_word = random.choice(words)
    
    request.session['captcha_answer'] = captcha_word
    
    return render(request, 'security/captcha_challenge.html', {
        'captcha_word': captcha_word,
        'timestamp': time.time(),
        'form_hash': hashlib.sha256(f"{time.time()}:{captcha_word}".encode()).hexdigest()[:16]
    })


def rate_limited(request):
    """Display rate limit message"""
    return render(request, 'security/rate_limited_enhanced.html', {
        'retry_after': 3600,  # 1 hour
        'limit_type': request.GET.get('type', 'general')
    })


def ip_change_detected(request):
    """Handle IP address change detection"""
    return render(request, 'security/ip_change_detected.html', {
        'support_contact': 'support@marketplace.onion'
    })


def session_expired(request):
    """Handle session expiration"""
    return render(request, 'security/session_expired.html', {
        'login_url': '/accounts/login/',
        'timeout_reason': request.GET.get('reason', 'inactivity')
    })


@login_required
def user_security_dashboard(request):
    """User security dashboard with risk assessment"""
    from wallets.models import AuditLog
    from .utils import calculate_security_score, detect_suspicious_patterns
    
    security_score = calculate_security_score(request.user)
    
    recent_logs = AuditLog.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    login_analysis = detect_suspicious_patterns(
        request.user, 
        'login',
        {'user_agent': request.META.get('HTTP_USER_AGENT', '')}
    )
    
    context = {
        'security_score': security_score,
        'recent_logs': recent_logs,
        'login_analysis': login_analysis,
    }
    
    return render(request, 'security/user_dashboard.html', context)


@login_required
@csrf_protect
def security_settings(request):
    """User security settings management"""
    from .forms import SecuritySettingsForm
    from .utils import log_security_event
    
    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST, user=request.user)
        if form.is_valid():
            user = request.user
            
            if hasattr(user, 'profile'):
                profile = user.profile
                profile.security_notifications = form.cleaned_data.get('security_notifications', True)
                profile.login_notifications = form.cleaned_data.get('login_notifications', True)
                profile.save()
            
            log_security_event(
                user,
                'settings_change',
                {
                    'changed_fields': list(form.changed_data),
                    'security_notifications': form.cleaned_data.get('security_notifications'),
                    'login_notifications': form.cleaned_data.get('login_notifications')
                },
                risk_score=5
            )
            
            messages.success(request, 'Security settings updated successfully!')
            return redirect('security:settings')
    else:
        initial_data = {}
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            initial_data = {
                'security_notifications': getattr(profile, 'security_notifications', True),
                'login_notifications': getattr(profile, 'login_notifications', True),
            }
        form = SecuritySettingsForm(initial=initial_data, user=request.user)
    
    return render(request, 'security/settings.html', {'form': form})


def security_verification(request):
    """High-risk account verification"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    import secrets
    verification_code = secrets.token_hex(8).upper()
    request.session['security_verification_code'] = verification_code
    request.session['security_verification_expires'] = (
        timezone.now() + timezone.timedelta(minutes=10)
    ).timestamp()
    
    if request.method == 'POST':
        submitted_code = request.POST.get('verification_code', '').strip().upper()
        stored_code = request.session.get('security_verification_code')
        expires = request.session.get('security_verification_expires')
        
        if not stored_code or not expires:
            messages.error(request, "Verification session expired. Please try again.")
            return redirect('security:security_verification')
        
        if timezone.now().timestamp() > expires:
            messages.error(request, "Verification code expired. Please try again.")
            return redirect('security:security_verification')
        
        if submitted_code == stored_code:
            request.session['high_risk_verified'] = True
            request.session['high_risk_verified_time'] = timezone.now().timestamp()
            
            request.session.pop('security_verification_code', None)
            request.session.pop('security_verification_expires', None)
            
            messages.success(request, "Security verification successful.")
            return redirect('wallets:dashboard')
        else:
            messages.error(request, "Invalid verification code. Please try again.")
    
    context = {
        'verification_code': verification_code
    }
    return render(request, 'security/security_verification.html', context)


def security_status_api(request):
    """API endpoint for security status"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    data = {
        'security_score': calculate_user_security_score(request.user),
        'two_fa_enabled': getattr(request.user.wallet, 'two_fa_enabled', False) if hasattr(request.user, 'wallet') else False,
        'pgp_enabled': bool(request.user.pgp_public_key),
        'recent_alerts': 0  # Will implement with proper SecurityEvent model
    }
    return JsonResponse(data)


def calculate_user_security_score(user):
    """Calculate security score for user"""
    score = 50  # Base score
    
    if hasattr(user, 'wallet') and user.wallet.two_fa_enabled:
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
