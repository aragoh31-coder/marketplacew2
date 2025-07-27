from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from decimal import Decimal
from wallets.models import Wallet, WithdrawalRequest
import random
import time

SEGS = 12


def log_user_action(request, action, details=None):
    """Log user actions for audit trail"""
    pass

@login_required
def dashboard(request):
    """Wallet dashboard view"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    withdrawal_requests = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'wallet': wallet,
        'withdrawal_requests': withdrawal_requests,
    }
    
    return render(request, 'wallets/dashboard.html', context)

@login_required
@ratelimit(key='user', rate='3/m', block=True)
def request_withdrawal(request):
    if request.method == 'POST':
        user_answer = request.POST.get('segment', '')
        hmac_token = request.POST.get('captcha_token', '')
        timestamp = request.POST.get('captcha_timestamp', '')
        pow_challenge = request.POST.get('pow_challenge', '')
        pow_nonce = request.POST.get('pow_nonce', '')
        
        try:
            user_answer = int(user_answer)
            timestamp = int(timestamp)
        except (ValueError, TypeError):
            user_answer = -1
            timestamp = 0
        
        from apps.security.captcha_oneclick.utils import validate_captcha_submission, generate_captcha_with_tokens
        is_valid, error_msg = validate_captcha_submission(
            user_answer, hmac_token, timestamp, pow_challenge, pow_nonce
        )
        
        if not is_valid:
            captcha_data = generate_captcha_with_tokens()
            return render(request, 'wallets/withdraw.html', {
                'captcha_image': captcha_data['image'],
                'captcha_token': captcha_data['hmac_token'],
                'captcha_timestamp': captcha_data['timestamp'],
                'pow_challenge': captcha_data['pow_challenge'],
                'SEGS': captcha_data['segments'],
                'error': f'CAPTCHA validation failed: {error_msg}'
            })

        amount = Decimal(request.POST.get('amount'))
        address = request.POST.get('address')

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)

            if amount <= 0 or amount > wallet.balance:
                messages.error(request, "Invalid amount")
                return redirect('wallets:withdraw')

            wallet.balance -= amount
            wallet.save()
            WithdrawalRequest.objects.create(user=request.user, amount=amount, address=address)

        messages.success(request, "Withdrawal request submitted successfully")
        return redirect('wallets:dashboard')

    from apps.security.captcha_oneclick.utils import generate_captcha_with_tokens
    captcha_data = generate_captcha_with_tokens()
    return render(request, 'wallets/withdraw.html', {
        'captcha_image': captcha_data['image'],
        'captcha_token': captcha_data['hmac_token'],
        'captcha_timestamp': captcha_data['timestamp'],
        'pow_challenge': captcha_data['pow_challenge'],
        'SEGS': captcha_data['segments']
    })


@login_required
def convert(request):
    """Handle currency conversion"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    context = {
        'wallet': wallet,
    }
    
    return render(request, 'wallets/convert.html', context)


@login_required
def deposit_info(request, currency):
    """Show deposit address"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    context = {
        'currency': currency,
        'wallet': wallet,
    }
    
    return render(request, 'wallets/deposit.html', context)


@login_required
def security_settings(request):
    """Manage wallet security settings"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    context = {
        'wallet': wallet,
    }
    
    return render(request, 'wallets/security_settings.html', context)


@login_required
def transaction_history(request):
    """View transaction history"""
    context = {}
    
    return render(request, 'wallets/transactions.html', context)


@login_required
def withdrawal_status(request):
    """View withdrawal request status"""
    withdrawal_requests = WithdrawalRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    return render(request, 'wallets/withdrawal_status.html', {
        'withdrawal_requests': withdrawal_requests
    })


@login_required
def withdrawal_detail(request, request_id):
    """Detailed view of withdrawal request"""
    withdrawal_request = get_object_or_404(
        WithdrawalRequest,
        id=request_id,
        user=request.user
    )
    
    return render(request, 'wallets/withdrawal_detail.html', {
        'withdrawal_request': withdrawal_request
    })


@login_required
@require_http_methods(["POST"])
def cancel_withdrawal(request, request_id):
    """Cancel pending withdrawal request"""
    withdrawal_request = get_object_or_404(
        WithdrawalRequest,
        id=request_id,
        user=request.user,
        status='pending'
    )
    
    withdrawal_request.status = 'cancelled'
    withdrawal_request.save()
    
    log_user_action(request, 'withdrawal_cancelled', {
        'withdrawal_id': withdrawal_request.pk,
        'amount': str(withdrawal_request.amount)
    })
    
    messages.success(request, 'Withdrawal request cancelled successfully.')
    return redirect('wallets:withdrawal_status')
