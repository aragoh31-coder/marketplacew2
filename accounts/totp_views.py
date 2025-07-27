from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.contrib.auth import login
from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .totp_forms import TOTPSetupForm, TOTPVerificationForm, TOTPDisableForm, BackupCodesRegenerateForm
from core.logging.audit_logger import audit_logger
import random
import time

@login_required
@ratelimit(key='ip', rate='5/m', block=True)
def totp_setup(request):
    if request.user.totp_enabled:
        messages.info(request, "Two-factor authentication is already enabled.")
        return redirect('accounts:totp_settings')

    request.user.generate_totp_secret()

    if request.method == 'POST':
        picked = int(request.POST.get('segment', -1))
        exp = request.session.get('captcha_expected', {})
        if time.time() - exp.get('ts',0) > 120 or picked != exp.get('segment'):
            form = TOTPSetupForm(request.user, request.POST)
            from apps.security.captcha_oneclick.utils import make_cut_circle
            missing = random.randrange(12)
            img_b64, _ = make_cut_circle(missing)
            request.session['captcha_expected'] = {'segment': missing, 'ts': time.time()}
            return render(request, 'accounts/totp_setup.html', {
                'form': form,
                'manual_entry_key': request.user.totp_secret,
                'captcha_image': img_b64,
                'SEGS': 12,
                'error': 'Invalid selection—try again.'
            })
        del request.session['captcha_expected']

        form = TOTPSetupForm(request.user, request.POST)
        if form.is_valid():
            request.user.totp_enabled = True
            request.user.save(update_fields=['totp_enabled'])

            backup_codes = request.user.generate_backup_codes()

            audit_logger.log_user_action(
                user=request.user,
                action='totp_enabled',
                details={'method': 'authenticator_app'},
                request=request,
                risk_level='medium'
            )

            request.session.flush()
            login(request, request.user)

            messages.success(request, "Two-factor authentication enabled successfully!")
            return render(request, 'accounts/totp_backup_codes.html', {
                'backup_codes': backup_codes,
                'is_setup': True
            })
    else:
        form = TOTPSetupForm(request.user)

    from apps.security.captcha_oneclick.utils import make_cut_circle
    missing = random.randrange(12)
    img_b64, _ = make_cut_circle(missing)
    request.session['captcha_expected'] = {'segment': missing, 'ts': time.time()}
    return render(request, 'accounts/totp_setup.html', {
        'form': form,
        'manual_entry_key': request.user.totp_secret,
        'captcha_image': img_b64,
        'SEGS': 12
    })

@login_required
def totp_settings(request):
    """TOTP settings management"""
    if not request.user.totp_enabled:
        return redirect('accounts:totp_setup')
    
    backup_codes_count = len(request.user.totp_backup_codes)
    
    return render(request, 'accounts/totp_settings.html', {
        'backup_codes_count': backup_codes_count
    })

@login_required
def totp_disable(request):
    """Disable TOTP 2FA"""
    if not request.user.totp_enabled:
        messages.info(request, "Two-factor authentication is not enabled.")
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = TOTPDisableForm(request.user, request.POST)
        if form.is_valid():
            request.user.disable_totp()
            
            audit_logger.log_user_action(
                user=request.user,
                action='totp_disabled',
                details={'method': 'user_request'},
                request=request,
                risk_level='high'
            )
            
            messages.success(request, "Two-factor authentication has been disabled.")
            return redirect('accounts:profile')
    else:
        form = TOTPDisableForm(request.user)
    
    return render(request, 'accounts/totp_disable.html', {
        'form': form
    })

@login_required
def regenerate_backup_codes(request):
    """Regenerate backup codes"""
    if not request.user.totp_enabled:
        messages.error(request, "Two-factor authentication is not enabled.")
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = TOTPDisableForm(request.user, request.POST)
        if form.is_valid():
            backup_codes = request.user.generate_backup_codes()
            
            audit_logger.log_user_action(
                user=request.user,
                action='backup_codes_regenerated',
                details={'codes_count': len(backup_codes)},
                request=request,
                risk_level='medium'
            )
            
            messages.success(request, "New backup codes have been generated. Please save them securely.")
            
            return render(request, 'accounts/totp_backup_codes.html', {
                'backup_codes': backup_codes,
                'is_regeneration': True
            })
    else:
        form = TOTPDisableForm(request.user)
    
    return render(request, 'accounts/regenerate_backup_codes.html', {
        'form': form
    })

def totp_verify(request):
    """Verify TOTP during login process"""
    user_id = request.session.get('totp_user_id')
    if not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect('accounts:login')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Invalid session. Please log in again.")
        return redirect('accounts:login')
    
    if request.method == 'POST':
        form = TOTPVerificationForm(user, request.POST)
        if form.is_valid():
            from django.contrib.auth import login
            login(request, user)
            
            request.session.pop('totp_user_id', None)
            request.session.pop('totp_required', None)
            
            audit_logger.log_user_action(
                user=user,
                action='totp_login_success',
                details={'method': 'totp_verification'},
                request=request,
                risk_level='low'
            )
            
            messages.success(request, f"Welcome back, {user.username}!")
            
            next_url = request.session.pop('login_redirect_url', '/')
            return redirect(next_url)
        else:
            audit_logger.log_security_event(
                event_type='totp_verification_failed',
                risk_level='medium',
                details={'username': user.username},
                user=user,
                request=request
            )
    else:
        form = TOTPVerificationForm(user)
    
    return render(request, 'accounts/verify_totp.html', {
        'form': form,
        'user': user
    })

@require_http_methods(["POST"])
@login_required
def test_totp(request):
    """Test TOTP token (AJAX endpoint)"""
    if not request.user.totp_secret:
        return JsonResponse({'valid': False, 'error': 'TOTP not configured'})
    
    token = request.POST.get('token', '').strip()
    
    if len(token) != 6 or not token.isdigit():
        return JsonResponse({'valid': False, 'error': 'Invalid token format'})
    
    is_valid = request.user.verify_totp(token)
    
    return JsonResponse({
        'valid': is_valid,
        'message': 'Token is valid!' if is_valid else 'Invalid token'
    })
