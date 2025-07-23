from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import re
import hashlib
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger('wallet.utils')


def check_rate_limit(request, action, max_attempts=5, window=3600):
    """Check if user has exceeded rate limit for specific action"""
    if not request.user.is_authenticated:
        return False
    
    cache_key = f'rate_limit:{request.user.id}:{action}'
    attempts = cache.get(cache_key, 0)
    
    if attempts >= max_attempts:
        logger.warning(f"Rate limit exceeded for user {request.user.username} on action {action}")
        return False
    
    cache.set(cache_key, attempts + 1, window)
    return True


def send_withdrawal_notification(withdrawal_request):
    """Send notification about withdrawal request"""
    try:
        subject = f"Withdrawal Request #{withdrawal_request.id} Submitted"
        message = render_to_string('wallets/emails/withdrawal_submitted.txt', {
            'withdrawal': withdrawal_request,
            'user': withdrawal_request.user
        })
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [withdrawal_request.user.email],
            fail_silently=False
        )
        
        admin_subject = f"New Withdrawal Request #{withdrawal_request.id}"
        admin_message = render_to_string('wallets/emails/withdrawal_admin.txt', {
            'withdrawal': withdrawal_request
        })
        
        admin_emails = [email for name, email in settings.ADMINS]
        if admin_emails:
            send_mail(
                admin_subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=False
            )
            
    except Exception as e:
        logger.error(f"Failed to send withdrawal notification: {str(e)}")


def validate_crypto_address(address, currency):
    """Validate cryptocurrency address format"""
    if currency == 'btc':
        patterns = [
            r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$',  # Legacy
            r'^bc1[a-z0-9]{39,59}$',  # Bech32
            r'^bc1[a-z0-9]{59,87}$'   # Bech32m
        ]
        return any(re.match(pattern, address) for pattern in patterns)
    
    elif currency == 'xmr':
        return re.match(r'^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$', address) is not None
    
    return False


def get_client_ip(request):
    """Get client IP address - returns None for privacy"""
    return None


def calculate_transaction_fee(currency, amount):
    """Calculate transaction fee for withdrawal"""
    if currency == 'btc':
        return amount * 0.001  # 0.1% fee
    elif currency == 'xmr':
        return amount * 0.0005  # 0.05% fee
    return 0


def format_crypto_amount(amount, currency):
    """Format cryptocurrency amount for display"""
    if currency == 'btc':
        return f"{amount:.8f} BTC"
    elif currency == 'xmr':
        return f"{amount:.12f} XMR"
    return f"{amount} {currency.upper()}"


def send_discrepancy_alert(wallet, balance_check):
    """Send balance discrepancy alert to administrators"""
    try:
        send_mail(
            subject=f'Wallet Balance Discrepancy - User {wallet.user.username}',
            message=f'''
A balance discrepancy has been detected in wallet {wallet.id}.

User: {wallet.user.username}
Wallet ID: {wallet.id}

Discrepancy Details:
{balance_check.discrepancy_details}

Please investigate immediately.
            '''.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Failed to send discrepancy alert: {str(e)}")


def anonymize_ip_address(ip_address):
    """Anonymize IP address for privacy protection"""
    if not ip_address:
        return 'unknown'
    
    return hashlib.sha256(ip_address.encode()).hexdigest()[:16]


def check_withdrawal_velocity(user):
    """Check for suspicious withdrawal velocity patterns"""
    from .models import WithdrawalRequest
    from django.utils import timezone
    from datetime import timedelta
    
    recent_withdrawals = WithdrawalRequest.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    daily_withdrawals = WithdrawalRequest.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    if recent_withdrawals >= 5:  # More than 5 in an hour
        return True, "Too many withdrawals in the last hour"
    
    if daily_withdrawals >= 20:  # More than 20 in a day
        return True, "Too many withdrawals in the last 24 hours"
    
    return False, "Normal velocity"


def validate_withdrawal_security(user, amount, currency, address):
    """Comprehensive withdrawal security validation"""
    errors = []
    risk_factors = []
    risk_score = 0
    
    if not validate_crypto_address(address, currency):
        errors.append(f"Invalid {currency.upper()} address format")
        risk_score += 30
    
    velocity_check, velocity_reason = check_withdrawal_velocity(user)
    if velocity_check:
        errors.append(velocity_reason)
        risk_factors.append("High withdrawal velocity")
        risk_score += 25
    
    large_amount_thresholds = {
        'btc': Decimal('0.1'),
        'xmr': Decimal('10.0')
    }
    
    if amount > large_amount_thresholds.get(currency, Decimal('0')):
        risk_factors.append(f"Large {currency.upper()} amount")
        risk_score += 20
    
    from .models import WithdrawalRequest
    previous_use = WithdrawalRequest.objects.filter(
        user=user,
        address=address,
        status='completed'
    ).exists()
    
    if not previous_use:
        risk_factors.append("New withdrawal address")
        risk_score += 15
    
    if user.date_joined > timezone.now() - timezone.timedelta(days=7):
        risk_factors.append("New account")
        risk_score += 30
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'risk_factors': risk_factors,
        'risk_score': risk_score,
        'manual_review_required': risk_score >= 40
    }
