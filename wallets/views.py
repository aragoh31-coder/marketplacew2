from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseForbidden
from decimal import Decimal
from wallets.models import Wallet, WithdrawalRequest
from core.security.captcha_cutcircle import init_captcha_session, validate_captcha
import random
import time


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
        click_x = request.POST.get('captcha_click.x')
        click_y = request.POST.get('captcha_click.y')
        
        if not click_x or not click_y or not validate_captcha(request, click_x, click_y):
            img_b64 = init_captcha_session(request)
            return render(request, 'wallets/withdraw.html', {
                'captcha_img': img_b64,
                'error': 'Captcha failed'
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

    img_b64 = init_captcha_session(request)
    return render(request, 'wallets/withdraw.html', {
        'captcha_img': img_b64
    })


@login_required
@ratelimit(key='user', rate='10/m', block=True)
def convert(request):
    """Handle currency conversion with atomic transactions"""
    if request.method == 'POST':
        from_currency = request.POST.get('from_currency')
        to_currency = request.POST.get('to_currency')
        amount = Decimal(request.POST.get('amount', '0'))
        
        if amount <= 0:
            messages.error(request, "Invalid amount")
            return redirect('wallets:convert')
            
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            
            if from_currency == 'btc' and amount > wallet.btc_balance:
                messages.error(request, "Insufficient BTC balance")
                return redirect('wallets:convert')
            elif from_currency == 'xmr' and amount > wallet.xmr_balance:
                messages.error(request, "Insufficient XMR balance")
                return redirect('wallets:convert')
            
            if from_currency == 'btc' and to_currency == 'xmr':
                rate = Decimal('15.5')  # Example rate
                converted_amount = amount * rate
                wallet.btc_balance -= amount
                wallet.xmr_balance += converted_amount
            elif from_currency == 'xmr' and to_currency == 'btc':
                rate = Decimal('0.064')  # Example rate
                converted_amount = amount * rate
                wallet.xmr_balance -= amount
                wallet.btc_balance += converted_amount
            else:
                messages.error(request, "Invalid currency pair")
                return redirect('wallets:convert')
                
            wallet.save()
            
            log_user_action(request, 'currency_conversion', {
                'from_currency': from_currency,
                'to_currency': to_currency,
                'amount': str(amount),
                'converted_amount': str(converted_amount),
                'rate': str(rate)
            })
            
        messages.success(request, f"Converted {amount} {from_currency.upper()} to {converted_amount} {to_currency.upper()}")
        return redirect('wallets:dashboard')
    
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
    """Cancel pending withdrawal request with atomic transaction"""
    with transaction.atomic():
        withdrawal_request = get_object_or_404(
            WithdrawalRequest,
            id=request_id,
            user=request.user,
            status='pending'
        )
        
        wallet = Wallet.objects.select_for_update().get(user=request.user)
        wallet.balance += withdrawal_request.amount
        wallet.save()
        
        withdrawal_request.status = 'cancelled'
        withdrawal_request.save()
        
        log_user_action(request, 'withdrawal_cancelled', {
            'withdrawal_id': withdrawal_request.pk,
            'amount': str(withdrawal_request.amount)
        })
    
    messages.success(request, 'Withdrawal request cancelled successfully.')
    return redirect('wallets:withdrawal_status')
