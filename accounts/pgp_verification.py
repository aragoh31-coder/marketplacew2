import secrets
import json
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .pgp_service import PGPService
from .forms import PGPKeyForm


@login_required
def pgp_settings(request):
    """Enhanced PGP settings with verification step"""
    if request.method == 'POST':
        if 'verify_code' in request.POST:
            return pgp_verify_key(request)
        
        form = PGPKeyForm(request.POST)
        if form.is_valid():
            request.session['temp_pgp_key'] = form.cleaned_data['pgp_public_key']
            request.session['temp_pgp_fingerprint'] = form.fingerprint
            request.session['temp_pgp_login_enabled'] = form.cleaned_data['enable_pgp_login']
            
            verification_code = secrets.token_urlsafe(16)
            request.session['pgp_verification_code'] = verification_code
            request.session['pgp_verification_expires'] = (
                timezone.now() + timezone.timedelta(minutes=10)
            ).isoformat()
            
            pgp_service = PGPService()
            
            verification_message = (
                f"PGP Key Verification\n\n"
                f"Please decrypt this message to verify your key.\n"
                f"Verification Code: {verification_code}\n\n"
                f"Enter only the verification code above."
            )
            
            encrypt_result = pgp_service.encrypt_message(
                verification_message,
                form.fingerprint
            )
            
            if encrypt_result['success']:
                return render(request, 'accounts/pgp_verify.html', {
                    'encrypted_message': encrypt_result['encrypted_message'],
                    'fingerprint': form.fingerprint[:8] + '...' + form.fingerprint[-8:],
                    'key_info': getattr(form, 'key_info', {}),
                })
            else:
                messages.error(
                    request, 
                    f'Failed to encrypt verification message: {encrypt_result["error"]}'
                )
    else:
        form = PGPKeyForm(initial={
            'pgp_public_key': request.user.pgp_public_key,
            'enable_pgp_login': request.user.pgp_login_enabled
        })
    
    return render(request, 'accounts/pgp_settings.html', {
        'form': form,
        'has_pgp': bool(request.user.pgp_public_key),
        'pgp_fingerprint': request.user.pgp_fingerprint
    })


@login_required
def pgp_verify_key(request):
    """Verify PGP key by checking decryption capability"""
    if request.method == 'POST':
        submitted_code = request.POST.get('verify_code', '').strip()
        
        stored_code = request.session.get('pgp_verification_code')
        expires = request.session.get('pgp_verification_expires')
        temp_key = request.session.get('temp_pgp_key')
        temp_fingerprint = request.session.get('temp_pgp_fingerprint')
        temp_login_enabled = request.session.get('temp_pgp_login_enabled', False)
        
        if not all([stored_code, expires, temp_key]):
            messages.error(request, 'Verification session expired. Please try again.')
            return redirect('accounts:pgp_settings')
        
        from dateutil import parser
        if timezone.now() > parser.parse(expires):
            messages.error(request, 'Verification code expired. Please try again.')
            for key in ['pgp_verification_code', 'pgp_verification_expires', 
                       'temp_pgp_key', 'temp_pgp_fingerprint', 'temp_pgp_login_enabled']:
                request.session.pop(key, None)
            return redirect('accounts:pgp_settings')
        
        if submitted_code == stored_code:
            request.user.pgp_public_key = temp_key
            request.user.pgp_fingerprint = temp_fingerprint
            request.user.pgp_login_enabled = temp_login_enabled
            request.user.save()
            
            for key in ['pgp_verification_code', 'pgp_verification_expires', 
                       'temp_pgp_key', 'temp_pgp_fingerprint', 'temp_pgp_login_enabled']:
                request.session.pop(key, None)
            
            messages.success(request, 'PGP key verified and saved successfully!')
            
            if temp_login_enabled:
                messages.info(
                    request, 
                    'PGP 2FA is now active. You will need to decrypt a challenge on your next login.'
                )
            
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Invalid verification code. Please check your decryption.')
            
            pgp_service = PGPService()
            verification_message = (
                f"PGP Key Verification\n\n"
                f"Please decrypt this message to verify your key.\n"
                f"Verification Code: {stored_code}\n\n"
                f"Enter only the verification code above."
            )
            
            encrypt_result = pgp_service.encrypt_message(
                verification_message,
                temp_fingerprint
            )
            
            return render(request, 'accounts/pgp_verify.html', {
                'encrypted_message': encrypt_result['encrypted_message'],
                'fingerprint': temp_fingerprint[:8] + '...' + temp_fingerprint[-8:],
                'error': 'Invalid verification code. Please try again.',
            })
    
    return redirect('accounts:pgp_settings')
