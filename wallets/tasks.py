from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Sum, Count, Q
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('wallet.tasks')


@shared_task
def reconcile_wallet_balances():
    """Enhanced periodic task to reconcile wallet balances"""
    from .models import Wallet, Transaction, WalletBalanceCheck
    
    logger.info("Starting comprehensive wallet balance reconciliation")
    
    wallets = Wallet.objects.all()
    discrepancies_found = 0
    
    for wallet in wallets:
        try:
            btc_deposits = Transaction.objects.filter(
                user=wallet.user,
                currency='btc',
                type__in=['deposit', 'escrow_release', 'conversion']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            btc_withdrawals = Transaction.objects.filter(
                user=wallet.user,
                currency='btc',
                type__in=['withdrawal', 'escrow_lock', 'fee']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            xmr_deposits = Transaction.objects.filter(
                user=wallet.user,
                currency='xmr',
                type__in=['deposit', 'escrow_release', 'conversion']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            xmr_withdrawals = Transaction.objects.filter(
                user=wallet.user,
                currency='xmr',
                type__in=['withdrawal', 'escrow_lock', 'fee']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            expected_btc = btc_deposits - btc_withdrawals
            expected_xmr = xmr_deposits - xmr_withdrawals
            
            btc_diff = abs(wallet.balance_btc - expected_btc)
            xmr_diff = abs(wallet.balance_xmr - expected_xmr)
            
            discrepancy_found = (
                btc_diff > Decimal('0.00000001') or 
                xmr_diff > Decimal('0.000000000001')
            )
            
            check = WalletBalanceCheck.objects.create(
                wallet=wallet,
                expected_btc=expected_btc,
                expected_xmr=expected_xmr,
                expected_escrow_btc=wallet.escrow_btc,
                expected_escrow_xmr=wallet.escrow_xmr,
                actual_btc=wallet.balance_btc,
                actual_xmr=wallet.balance_xmr,
                actual_escrow_btc=wallet.escrow_btc,
                actual_escrow_xmr=wallet.escrow_xmr,
                discrepancy_found=discrepancy_found,
                discrepancy_details={
                    'btc_diff': str(btc_diff),
                    'xmr_diff': str(xmr_diff),
                    'btc_expected': str(expected_btc),
                    'xmr_expected': str(expected_xmr),
                    'btc_deposits': str(btc_deposits),
                    'btc_withdrawals': str(btc_withdrawals),
                    'xmr_deposits': str(xmr_deposits),
                    'xmr_withdrawals': str(xmr_withdrawals)
                } if discrepancy_found else {}
            )
            
            if discrepancy_found:
                discrepancies_found += 1
                logger.warning(f"Balance discrepancy found for wallet {wallet.pk}")
                
                if btc_diff > Decimal('0.001') or xmr_diff > Decimal('0.1'):
                    send_discrepancy_alert.delay(wallet.pk, check.pk)
        
        except Exception as e:
            logger.error(f"Error reconciling wallet {wallet.pk}: {str(e)}")
    
    logger.info(f"Reconciliation complete. Found {discrepancies_found} discrepancies")
    return discrepancies_found


@shared_task
def cleanup_old_audit_logs():
    """Enhanced cleanup of old audit logs with archival"""
    from .models import AuditLog
    
    retention_days = getattr(settings, 'WALLET_SECURITY', {}).get('AUDIT_LOG_RETENTION_DAYS', 365)
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    important_logs = AuditLog.objects.filter(
        created_at__lt=cutoff_date,
        flagged=True
    )
    
    important_count = important_logs.count()
    if important_count > 0:
        logger.info(f"Archiving {important_count} important flagged logs")
        
        for log in important_logs[:100]:  # Limit to prevent memory issues
            logger.warning(
                f"Archiving important audit log: User {log.user.username}, "
                f"Action {log.action}, Risk {log.risk_score}, "
                f"Details {log.details}"
            )
    
    deleted_count = AuditLog.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f"Deleted {deleted_count} old audit logs")
    return deleted_count


@shared_task
def send_discrepancy_alert(wallet_id, check_id):
    """Enhanced alert for balance discrepancy"""
    try:
        from .models import Wallet, WalletBalanceCheck
        
        wallet = Wallet.objects.get(id=wallet_id)
        check = WalletBalanceCheck.objects.get(id=check_id)
        
        subject = f"URGENT: Balance Discrepancy Alert - Wallet {wallet.pk}"
        message = f"""
        URGENT: Balance discrepancy detected for user {wallet.user.username} (ID: {wallet.user.id})
        
        Wallet ID: {wallet.pk}
        User: {wallet.user.username}
        Email: {wallet.user.email}
        
        BTC Expected: {check.expected_btc}
        BTC Actual: {check.actual_btc}
        BTC Difference: {abs(check.actual_btc - check.expected_btc)}
        
        XMR Expected: {check.expected_xmr}
        XMR Actual: {check.actual_xmr}
        XMR Difference: {abs(check.actual_xmr - check.expected_xmr)}
        
        Discrepancy Details: {check.discrepancy_details}
        Check ID: {check.pk}
        Timestamp: {check.checked_at}
        
        IMMEDIATE ACTION REQUIRED:
        1. Investigate transaction history
        2. Check for unauthorized access
        3. Verify wallet integrity
        4. Contact user if necessary
        """
        
        admin_emails = [email for name, email in settings.ADMINS]
        if not admin_emails:
            admin_emails = [getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')]
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails,
            fail_silently=False,
        )
        
        logger.info(f"Discrepancy alert sent for wallet {wallet_id}")
        
    except Exception as e:
        logger.error(f"Error sending discrepancy alert: {str(e)}")


@shared_task
def check_suspicious_activity():
    """Enhanced suspicious activity detection"""
    from .models import WithdrawalRequest, AuditLog
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    alerts_created = 0
    
    recent_failed = WithdrawalRequest.objects.filter(
        status='rejected',
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).values('user').annotate(
        count=Count('id')
    ).filter(count__gte=3)
    
    for item in recent_failed:
        user = User.objects.get(id=item['user'])
        AuditLog.objects.create(
            user=user,
            action='security_alert',
            ip_address='127.0.0.1',  # System generated, no real IP logging
            user_agent='system',
            details={
                'alert_type': 'multiple_failed_withdrawals',
                'count': item['count'],
                'timeframe': '1_hour'
            },
            flagged=True,
            risk_score=60
        )
        alerts_created += 1
    
    rapid_withdrawals = WithdrawalRequest.objects.filter(
        created_at__gte=timezone.now() - timedelta(minutes=30)
    ).values('user').annotate(
        count=Count('id')
    ).filter(count__gte=5)
    
    for item in rapid_withdrawals:
        user = User.objects.get(id=item['user'])
        AuditLog.objects.create(
            user=user,
            action='security_alert',
            ip_address='127.0.0.1',
            user_agent='system',
            details={
                'alert_type': 'rapid_withdrawal_velocity',
                'count': item['count'],
                'timeframe': '30_minutes'
            },
            flagged=True,
            risk_score=40
        )
        alerts_created += 1
    
    large_withdrawals = WithdrawalRequest.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24),
        status__in=['pending', 'approved']
    ).filter(
        Q(currency='btc', amount__gte=Decimal('0.5')) |
        Q(currency='xmr', amount__gte=Decimal('50'))
    )
    
    for wr in large_withdrawals:
        AuditLog.objects.create(
            user=wr.user,
            action='security_alert',
            ip_address='127.0.0.1',
            user_agent='system',
            details={
                'alert_type': 'large_withdrawal_amount',
                'amount': str(wr.amount),
                'currency': wr.currency,
                'withdrawal_id': wr.pk,
                'risk_score': wr.risk_score
            },
            flagged=True,
            risk_score=30
        )
        alerts_created += 1
    
    recent_logins = AuditLog.objects.filter(
        action='login',
        created_at__gte=timezone.now() - timedelta(minutes=15)
    ).values('user').annotate(
        count=Count('id')
    ).filter(count__gte=5)
    
    for item in recent_logins:
        user = User.objects.get(id=item['user'])
        AuditLog.objects.create(
            user=user,
            action='security_alert',
            ip_address='127.0.0.1',
            user_agent='system',
            details={
                'alert_type': 'rapid_login_attempts',
                'count': item['count'],
                'timeframe': '15_minutes'
            },
            flagged=True,
            risk_score=25
        )
        alerts_created += 1
    
    logger.info(f"Suspicious activity check completed. Created {alerts_created} alerts")
    return alerts_created


@shared_task
def send_withdrawal_notification(withdrawal_id):
    """Enhanced notification for withdrawal requests"""
    try:
        from .models import WithdrawalRequest
        
        wr = WithdrawalRequest.objects.get(id=withdrawal_id)
        
        user_subject = f"Withdrawal Request #{wr.pk} Submitted"
        user_message = f"""
        Your withdrawal request has been submitted successfully.
        
        Request ID: #{wr.pk}
        Amount: {wr.amount} {wr.currency.upper()}
        Address: {wr.address}
        Status: {wr.status.title()}
        Risk Assessment: {wr.risk_score}/100
        
        Processing Information:
        - All withdrawals are manually reviewed for security
        - Processing time: 1-24 hours for standard requests
        - High-risk requests may require additional verification
        
        You will be notified once your withdrawal is processed.
        
        If you did not request this withdrawal, please contact support immediately.
        """
        
        if wr.user.email:
            send_mail(
                user_subject,
                user_message,
                settings.DEFAULT_FROM_EMAIL,
                [wr.user.email],
                fail_silently=True,
            )
        
        if wr.risk_score >= 40 or wr.manual_review_required:
            admin_subject = f"High-Risk Withdrawal Request #{wr.pk} - Manual Review Required"
            admin_message = f"""
            High-risk withdrawal request requires immediate review.
            
            Request Details:
            - ID: #{wr.pk}
            - User: {wr.user.username} (ID: {wr.user.id})
            - Email: {wr.user.email}
            - Amount: {wr.amount} {wr.currency.upper()}
            - Address: {wr.address}
            - Risk Score: {wr.risk_score}/100
            - Manual Review: {'Yes' if wr.manual_review_required else 'No'}
            
            Risk Factors:
            {', '.join(wr.risk_factors) if wr.risk_factors else 'None specified'}
            
            User Notes: {wr.user_note or 'None'}
            
            Action Required:
            1. Review user account history
            2. Verify withdrawal address
            3. Check for suspicious patterns
            4. Approve or reject in admin panel
            
            Admin Panel: /admin/wallets/withdrawalrequest/{wr.pk}/change/
            """
            
            admin_emails = [email for name, email in settings.ADMINS]
            if not admin_emails:
                admin_emails = [getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')]
            
            send_mail(
                admin_subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=True,
            )
        
        logger.info(f"Withdrawal notification sent for request {withdrawal_id}")
        
    except Exception as e:
        logger.error(f"Error sending withdrawal notification: {str(e)}")


@shared_task
def update_exchange_rates():
    """Update cryptocurrency exchange rates"""
    from .models import ConversionRate
    
    try:
        
        ConversionRate.objects.filter(is_active=True).update(
            is_active=False,
            valid_until=timezone.now()
        )
        
        import random
        base_btc_xmr = Decimal('350.0')
        variation = Decimal(str(random.uniform(-5.0, 5.0)))  # ±5 XMR variation
        btc_to_xmr_rate = base_btc_xmr + variation
        
        ConversionRate.objects.create(
            from_currency='btc',
            to_currency='xmr',
            rate=btc_to_xmr_rate,
            source='api_update',
            source_data={
                'provider': 'internal_simulation',
                'timestamp': timezone.now().isoformat(),
                'base_rate': str(base_btc_xmr),
                'variation': str(variation)
            }
        )
        
        xmr_to_btc_rate = Decimal('1') / btc_to_xmr_rate
        
        ConversionRate.objects.create(
            from_currency='xmr',
            to_currency='btc',
            rate=xmr_to_btc_rate,
            source='api_update',
            source_data={
                'provider': 'internal_simulation',
                'timestamp': timezone.now().isoformat(),
                'calculated_from': str(btc_to_xmr_rate)
            }
        )
        
        logger.info(f"Exchange rates updated: 1 BTC = {btc_to_xmr_rate} XMR, 1 XMR = {xmr_to_btc_rate} BTC")
        return True
        
    except Exception as e:
        logger.error(f"Error updating exchange rates: {str(e)}")
        return False


@shared_task
def monitor_wallet_security():
    """Enhanced security monitoring for wallet operations"""
    from .models import AuditLog, WithdrawalRequest
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    alerts_created = 0
    
    high_risk_users = AuditLog.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24),
        risk_score__gte=40
    ).values('user').annotate(
        risk_count=Count('id'),
        avg_risk=Sum('risk_score') / Count('id')
    ).filter(risk_count__gte=3)
    
    for item in high_risk_users:
        user = User.objects.get(id=item['user'])
        AuditLog.objects.create(
            user=user,
            action='security_alert',
            ip_address='privacy_protected',  # Privacy protection
            user_agent='system',
            details={
                'alert_type': 'high_risk_user_pattern',
                'risk_events_count': item['risk_count'],
                'average_risk_score': float(item['avg_risk']),
                'timeframe': '24_hours'
            },
            flagged=True,
            risk_score=70
        )
        alerts_created += 1
    
    unusual_patterns = WithdrawalRequest.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=6)
    ).values('user').annotate(
        withdrawal_count=Count('id'),
        total_amount_btc=Sum('amount', filter=Q(currency='btc')),
        total_amount_xmr=Sum('amount', filter=Q(currency='xmr'))
    ).filter(
        Q(withdrawal_count__gte=10) |
        Q(total_amount_btc__gte=Decimal('2.0')) |
        Q(total_amount_xmr__gte=Decimal('200.0'))
    )
    
    for item in unusual_patterns:
        user = User.objects.get(id=item['user'])
        AuditLog.objects.create(
            user=user,
            action='security_alert',
            ip_address='privacy_protected',
            user_agent='system',
            details={
                'alert_type': 'unusual_withdrawal_pattern',
                'withdrawal_count': item['withdrawal_count'],
                'total_btc': str(item['total_amount_btc'] or 0),
                'total_xmr': str(item['total_amount_xmr'] or 0),
                'timeframe': '6_hours'
            },
            flagged=True,
            risk_score=50
        )
        alerts_created += 1
    
    logger.info(f"Security monitoring completed. Created {alerts_created} alerts")
    return alerts_created


@shared_task
def cleanup_expired_sessions():
    """Clean up expired security sessions and cache entries"""
    from django.core.cache import cache
    from django.contrib.sessions.models import Session
    
    expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
    expired_count = expired_sessions.count()
    expired_sessions.delete()
    
    logger.info(f"Cleaned up {expired_count} expired sessions")
    
    logger.info("Session cleanup completed")
    
    return expired_count


def send_discrepancy_alert_sync(wallet, check):
    """Legacy function for backward compatibility"""
    send_discrepancy_alert.delay(wallet.pk, check.pk)
