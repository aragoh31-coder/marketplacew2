from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from decimal import Decimal
from wallets.models import Wallet, WithdrawalRequest
from core.security.captcha import generate_captcha, validate_captcha


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
        if not validate_captcha(request):
            return HttpResponseForbidden("CAPTCHA failed")

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

    captcha_label, captcha_buttons = generate_captcha(request.session)
    return render(request, 'wallets/withdraw.html', {
        'captcha_label': captcha_label,
        'captcha_buttons': captcha_buttons
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
