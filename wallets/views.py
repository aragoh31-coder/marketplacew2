from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.db.models import Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden
from decimal import Decimal
import logging
from .models import Wallet, WithdrawalRequest


def log_user_action(request, action, details=None):
    """Log user actions for audit trail"""
    pass


@login_required
@csrf_protect
def dashboard(request):
    """Wallet dashboard with balance information"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    pending_withdrawals = WithdrawalRequest.objects.filter(
        user=request.user,
        status__in=['pending', 'reviewing', 'approved', 'processing']
    ).order_by('-created_at')[:5]
    
    recent_transactions = []
    
    btc_available = wallet.balance
    xmr_available = Decimal('0.00000000')
    
    last_check = None
    show_balance_warning = False
    
    from django.utils import timezone
    today = timezone.now().date()
    daily_btc_used = WithdrawalRequest.objects.filter(
        user=request.user,
        created_at__date=today,
        status__in=['approved', 'processing', 'completed']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    daily_xmr_used = Decimal('0')
    
    security_score = 0
    if hasattr(request.user, 'totp_secret') and request.user.totp_secret:
        security_score += 30
    if hasattr(request.user, 'pgp_public_key') and request.user.pgp_public_key:
        security_score += 25
    
    account_age = (timezone.now().date() - request.user.date_joined.date()).days
    if account_age >= 90:
        security_score += 20
    elif account_age >= 30:
        security_score += 15
    elif account_age >= 7:
        security_score += 10

    context = {
        'wallet': wallet,
        'btc_available': btc_available,
        'xmr_available': xmr_available,
        'pending_withdrawals': pending_withdrawals,
        'recent_transactions': recent_transactions,
        'show_balance_warning': show_balance_warning,
        'daily_btc_used': daily_btc_used,
        'daily_xmr_used': daily_xmr_used,
        'security_score': min(security_score, 100),
        'security_alerts': [],
    }
    
    return render(request, 'wallets/dashboard.html', context)


@login_required
@ratelimit(key='user', rate='3/m', block=True)
def request_withdrawal(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        address = request.POST.get('address')
        wallet = Wallet.objects.select_for_update().get(user=request.user)

        if amount <= 0 or amount > wallet.balance:
            messages.error(request, "Invalid amount")
            return redirect('wallets:withdraw')

        with transaction.atomic():
            wallet.balance -= amount
            wallet.save()
            WithdrawalRequest.objects.create(user=request.user, amount=amount, address=address)

        messages.success(request, "Withdrawal request submitted")
        return redirect('wallets:dashboard')

    return render(request, 'wallets/withdraw.html')


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
