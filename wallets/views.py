from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseForbidden
from decimal import Decimal
import pyotp
import qrcode
import io
import base64
import logging

from .models import (
    Wallet, WithdrawalRequest, Transaction, ConversionRate, AuditLog
)
from .forms import (
    WithdrawalForm, ConversionForm, TwoFactorForm, 
    WithdrawalPinForm, SecuritySettingsForm
)
from .utils import (
    check_rate_limit, send_withdrawal_notification,
    validate_crypto_address, get_client_ip
)
from adminpanel.models import SecurityAlert

logger = logging.getLogger('wallet.views')


def log_user_action(request, action, details=None):
    """Log user actions for audit trail"""
    AuditLog.objects.create(
        user=request.user,
        action=action,
        details=details or {}
    )


@login_required
@csrf_protect
def dashboard(request):
    """Wallet dashboard with balance information"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    pending_withdrawals = WithdrawalRequest.objects.filter(
        user=request.user,
        status__in=['pending', 'reviewing', 'approved', 'processing']
    ).order_by('-created_at')[:5]
    
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    btc_available = wallet.get_available_balance('btc')
    xmr_available = wallet.get_available_balance('xmr')
    
    last_check = wallet.walletbalancecheck_set.order_by('-checked_at').first()
    show_balance_warning = (
        last_check and 
        last_check.discrepancy_found and 
        not last_check.resolved
    )
    
    from django.utils import timezone
    today = timezone.now().date()
    daily_btc_used = WithdrawalRequest.objects.filter(
        user=request.user,
        currency='btc',
        created_at__date=today,
        status__in=['approved', 'processing', 'completed']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    daily_xmr_used = WithdrawalRequest.objects.filter(
        user=request.user,
        currency='xmr',
        created_at__date=today,
        status__in=['approved', 'processing', 'completed']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    security_score = 0
    if wallet.two_fa_enabled:
        security_score += 30
    if wallet.withdrawal_pin:
        security_score += 25
    if request.user.pgp_public_key:
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
    }
    
    security_alerts = SecurityAlert.objects.filter(
        user=request.user,
        is_resolved=False
    ).order_by('-created_at')[:5]
    
    context.update({
        'security_alerts': security_alerts,
    })
    
    return render(request, 'wallets/dashboard.html', context)


@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def withdraw(request):
    """Handle withdrawal requests with comprehensive security checks"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    if not check_rate_limit(request, 'withdraw', max_attempts=5, window=3600):
        messages.error(request, "Too many withdrawal attempts. Please try again later.")
        return redirect('wallets:dashboard')
    
    if request.method == 'POST':
        form = WithdrawalForm(request.POST, user=request.user)
        
        if form.is_valid():
            if wallet.two_fa_enabled:
                if not form.cleaned_data.get('two_fa_code'):
                    form.add_error('two_fa_code', '2FA code is required')
                else:
                    totp = pyotp.TOTP(wallet.two_fa_secret)
                    if not totp.verify(form.cleaned_data['two_fa_code']):
                        form.add_error('two_fa_code', 'Invalid 2FA code')
                        log_user_action(request, 'withdrawal_request', {
                            'status': 'failed',
                            'reason': 'invalid_2fa'
                        })
            
            if wallet.withdrawal_pin and form.cleaned_data.get('pin'):
                from django.contrib.auth.hashers import check_password
                if not check_password(form.cleaned_data['pin'], wallet.withdrawal_pin):
                    form.add_error('pin', 'Invalid PIN')
                    log_user_action(request, 'withdrawal_request', {
                        'status': 'failed',
                        'reason': 'invalid_pin'
                    })
            
            if not form.errors:
                try:
                    with transaction.atomic():
                        wr = WithdrawalRequest.objects.create(
                            user=request.user,
                            amount=form.cleaned_data['amount'],
                            currency=form.cleaned_data['currency'],
                            address=form.cleaned_data['address'],
                            user_note=form.cleaned_data.get('note', ''),
                            two_fa_verified=wallet.two_fa_enabled,
                            pin_verified=bool(wallet.withdrawal_pin)
                        )
                        
                        wr.calculate_risk_score()
                        wr.save()
                        
                        log_user_action(request, 'withdrawal_request', {
                            'status': 'success',
                            'withdrawal_id': wr.id,
                            'amount': str(wr.amount),
                            'currency': wr.currency,
                            'risk_score': wr.risk_score
                        })
                        
                        send_withdrawal_notification(wr)
                        
                        messages.success(
                            request, 
                            f"Withdrawal request #{wr.id} submitted successfully. "
                            f"You will be notified once it's processed."
                        )
                        
                        return redirect('wallets:dashboard')
                        
                except Exception as e:
                    logger.error(f"Error creating withdrawal: {str(e)}")
                    messages.error(request, "An error occurred. Please try again.")
    else:
        form = WithdrawalForm(user=request.user)
    
    btc_available = wallet.get_available_balance('btc')
    xmr_available = wallet.get_available_balance('xmr')
    
    btc_daily_remaining = wallet.daily_withdrawal_limit_btc - wallet.get_daily_withdrawal_total('btc')
    xmr_daily_remaining = wallet.daily_withdrawal_limit_xmr - wallet.get_daily_withdrawal_total('xmr')
    
    context = {
        'form': form,
        'wallet': wallet,
        'btc_available': btc_available,
        'xmr_available': xmr_available,
        'btc_daily_remaining': max(Decimal('0'), btc_daily_remaining),
        'xmr_daily_remaining': max(Decimal('0'), xmr_daily_remaining),
    }
    
    return render(request, 'wallets/withdraw.html', context)


@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def convert(request):
    """Handle currency conversion with real-time rates"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    if request.method == 'POST':
        form = ConversionForm(request.POST, user=request.user)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=request.user)
                    
                    from_currency = form.cleaned_data['from_currency']
                    to_currency = form.cleaned_data['to_currency']
                    amount = form.cleaned_data['amount']
                    
                    rate = ConversionRate.get_current_rate(from_currency, to_currency)
                    if not rate:
                        messages.error(request, "Conversion rate not available")
                        return redirect('wallets:convert')
                    
                    converted_amount = amount * rate
                    
                    available = wallet.get_available_balance(from_currency)
                    if amount > available:
                        messages.error(request, "Insufficient balance")
                        return redirect('wallets:convert')
                    
                    from_balance_field = f'balance_{from_currency}'
                    to_balance_field = f'balance_{to_currency}'
                    from_balance_before = getattr(wallet, from_balance_field)
                    to_balance_before = getattr(wallet, to_balance_field)
                    
                    setattr(wallet, from_balance_field, from_balance_before - amount)
                    setattr(wallet, to_balance_field, to_balance_before + converted_amount)
                    wallet.save()
                    
                    trans = Transaction.objects.create(
                        user=request.user,
                        type='conversion',
                        amount=amount,
                        currency=from_currency,
                        converted_amount=converted_amount,
                        converted_currency=to_currency,
                        conversion_rate=rate,
                        balance_before=from_balance_before,
                        balance_after=from_balance_before - amount,
                        reference=f"CONV-{timezone.now().timestamp()}",
                        metadata={
                            'rate_used': str(rate),
                            'from_balance_before': str(from_balance_before),
                            'from_balance_after': str(from_balance_before - amount),
                            'to_balance_before': str(to_balance_before),
                            'to_balance_after': str(to_balance_before + converted_amount)
                        }
                    )
                    
                    log_user_action(request, 'conversion', {
                        'transaction_id': trans.id,
                        'from_currency': from_currency,
                        'to_currency': to_currency,
                        'amount': str(amount),
                        'converted_amount': str(converted_amount),
                        'rate': str(rate)
                    })
                    
                    messages.success(
                        request,
                        f"Successfully converted {amount} {from_currency.upper()} "
                        f"to {converted_amount} {to_currency.upper()} "
                        f"at rate {rate}"
                    )
                    
                    return redirect('wallets:dashboard')
                    
            except Exception as e:
                logger.error(f"Conversion error: {str(e)}")
                messages.error(request, "An error occurred during conversion")
    else:
        form = ConversionForm(user=request.user)
    
    btc_to_xmr = ConversionRate.get_current_rate('btc', 'xmr')
    xmr_to_btc = ConversionRate.get_current_rate('xmr', 'btc')
    
    context = {
        'form': form,
        'wallet': wallet,
        'btc_available': wallet.get_available_balance('btc'),
        'xmr_available': wallet.get_available_balance('xmr'),
        'rates': {
            'btc_xmr': btc_to_xmr or 'N/A',
            'xmr_btc': xmr_to_btc or 'N/A',
        }
    }
    
    return render(request, 'wallets/convert.html', context)


from .models import DepositAddress
from .rpc_client import BitcoinRPC, MoneroRPC

@login_required
@csrf_protect
def deposit_info(request, currency):
    """
    Gets or creates a persistent deposit address for the user and displays it
    with a QR code.
    """
    if currency not in ['btc', 'xmr']:
        messages.error(request, "Invalid currency")
        return redirect('wallets:dashboard')

    wallet = get_object_or_404(Wallet, user=request.user)
    address_obj = DepositAddress.objects.filter(user=request.user, currency=currency).first()
    address = None
    error_message = None

    if address_obj:
        address = address_obj.address
    else:
        # No address found, generate a new one
        if currency == 'btc':
            rpc = BitcoinRPC()
            result = rpc.get_new_address(label=request.user.username)
        else: # currency == 'xmr'
            rpc = MoneroRPC()
            result = rpc.get_new_address()

        if result.get("success"):
            address = result["address"]
            DepositAddress.objects.create(
                user=request.user,
                currency=currency,
                address=address
            )
        else:
            error_message = f"Could not generate a new {currency.upper()} address at this time. Please try again later. Error: {result.get('error')}"
            logger.error(f"Failed to generate deposit address for {request.user.username}: {error_message}")
            messages.error(request, error_message)

    qr_code = None
    if address:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(address)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code = base64.b64encode(buffer.getvalue()).decode()

    context = {
        'currency': currency,
        'address': address,
        'qr_code': qr_code,
        'wallet': wallet,
        'error_message': error_message,
    }
    
    return render(request, 'wallets/deposit.html', context)


@login_required
@csrf_protect
def security_settings(request):
    """Manage wallet security settings"""
    wallet = get_object_or_404(Wallet, user=request.user)
    
    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST, instance=wallet)
        
        if form.is_valid():
            if form.cleaned_data.get('enable_2fa') and not wallet.two_fa_enabled:
                secret = pyotp.random_base32()
                wallet.two_fa_secret = secret
                wallet.two_fa_enabled = True
                
                totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
                    name=request.user.username,
                    issuer_name='Secure Marketplace'
                )
                
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(totp_uri)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                qr_code = base64.b64encode(buffer.getvalue()).decode()
                
                messages.info(
                    request,
                    "Please scan the QR code with your authenticator app"
                )
                
                return render(request, 'wallets/2fa_setup.html', {
                    'qr_code': qr_code,
                    'secret': secret
                })
            
            if form.cleaned_data.get('new_pin'):
                from django.contrib.auth.hashers import make_password
                wallet.withdrawal_pin = make_password(form.cleaned_data['new_pin'])
            
            wallet.save()
            form.save()
            
            log_user_action(request, 'settings_change', {
                'changed_fields': form.changed_data
            })
            
            messages.success(request, "Security settings updated successfully")
            return redirect('wallets:security_settings')
    else:
        form = SecuritySettingsForm(instance=wallet)
    
    context = {
        'form': form,
        'wallet': wallet,
    }
    
    return render(request, 'wallets/security_settings.html', context)


@login_required
@require_http_methods(["GET"])
def transaction_history(request):
    """View transaction history with filtering"""
    transactions = Transaction.objects.filter(user=request.user)
    
    tx_type = request.GET.get('type')
    if tx_type:
        transactions = transactions.filter(type=tx_type)
    
    currency = request.GET.get('currency')
    if currency:
        transactions = transactions.filter(currency=currency)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        transactions = transactions.filter(created_at__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__lte=date_to)
    
    from django.core.paginator import Paginator
    paginator = Paginator(transactions.order_by('-created_at'), 50)
    page = request.GET.get('page', 1)
    
    try:
        transactions_page = paginator.page(page)
    except:
        transactions_page = paginator.page(1)
    
    context = {
        'transactions': transactions_page,
        'type_choices': Transaction.TYPE_CHOICES,
        'filters': {
            'type': tx_type,
            'currency': currency,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
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
        'withdrawal_id': withdrawal_request.id,
        'amount': str(withdrawal_request.amount),
        'currency': withdrawal_request.currency
    })
    
    messages.success(request, 'Withdrawal request cancelled successfully.')
    return redirect('wallets:withdrawal_status')
