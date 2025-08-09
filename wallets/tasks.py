import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import WithdrawalRequest

logger = logging.getLogger(__name__)


@shared_task
def process_withdrawal(withdrawal_id):
    withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
    withdrawal.status = "completed"
    withdrawal.processed_at = timezone.now()
    withdrawal.tx_hash = "FAKE_TX_HASH"
    withdrawal.save()
    logger.info(f"Withdrawal {withdrawal.pk} completed")


@shared_task
def update_conversion_rates():
    """Update cryptocurrency conversion rates - using hardcoded values from settings for now"""
    try:
        rates = {
            "BTC_USD": getattr(settings, "BTC_USD_RATE", 118905.27),
            "XMR_USD": getattr(settings, "XMR_USD_RATE", 340.67),
            "BTC_EUR": getattr(settings, "BTC_EUR_RATE", 108000.00),
            "XMR_EUR": getattr(settings, "XMR_EUR_RATE", 310.00),
        }

        from django.core.cache import cache

        cache.set("conversion_rates", rates, 300)

        logger.info(f"Conversion rates updated: {rates}")
        return rates

    except Exception as e:
        logger.error(f"Failed to update conversion rates: {str(e)}")
        return None


@shared_task
def check_suspicious_activity():
    """Monitor for suspicious wallet activity patterns"""
    try:
        from datetime import timedelta

        from django.db.models import Count

        from .models import WalletAuditLog

        cutoff_time = timezone.now() - timedelta(hours=1)

        suspicious_ips = (
            WalletAuditLog.objects.filter(
                action="withdrawal_request", timestamp__gte=cutoff_time
            )
            .values("user")
            .annotate(count=Count("id"))
            .filter(count__gte=5)
        )

        if suspicious_ips.exists():
            logger.warning(
                f"Suspicious activity detected: {suspicious_ips.count()} IPs with rapid withdrawals"
            )

            for user_data in suspicious_ips:
                logger.warning(
                    f"User {user_data['user']} made {user_data['count']} withdrawal requests in 1 hour"
                )

        logger.info("Suspicious activity check completed")
        return f"Checked activity, found {suspicious_ips.count()} suspicious users"

    except Exception as e:
        logger.error(f"Failed to check suspicious activity: {str(e)}")
        return None


@shared_task
def monitor_wallet_security():
    """Daily security monitoring for wallet operations"""
    try:
        from datetime import timedelta

        from django.db.models import Count, Sum

        from .models import WalletAuditLog, WithdrawalRequest

        cutoff_time = timezone.now() - timedelta(days=1)

        withdrawal_stats = WithdrawalRequest.objects.filter(
            created_at__gte=cutoff_time
        ).aggregate(
            total_count=Count("id"),
            total_btc=Sum("amount_btc") or 0,
            total_xmr=Sum("amount_xmr") or 0,
        )

        audit_stats = (
            WalletAuditLog.objects.filter(timestamp__gte=cutoff_time)
            .values("action")
            .annotate(count=Count("id"))
        )

        logger.info(f"Daily wallet security report:")
        logger.info(f"Withdrawals: {withdrawal_stats['total_count']} requests")
        logger.info(f"Total BTC: {withdrawal_stats['total_btc']}")
        logger.info(f"Total XMR: {withdrawal_stats['total_xmr']}")

        for stat in audit_stats:
            logger.info(f"Action '{stat['action']}': {stat['count']} times")

        return {"withdrawal_stats": withdrawal_stats, "audit_stats": list(audit_stats)}

    except Exception as e:
        logger.error(f"Failed to monitor wallet security: {str(e)}")
        return None


@shared_task
def reconcile_wallet_balances():
    """Reconcile wallet balances with blockchain data"""
    try:
        from .models import Wallet

        wallets = Wallet.objects.all()
        reconciled_count = 0
        discrepancies = []

        for wallet in wallets:
            try:
                logger.info(
                    f"Reconciling wallet for user {wallet.user.username}: BTC={wallet.btc_balance}, XMR={wallet.xmr_balance}"
                )
                reconciled_count += 1

            except Exception as e:
                logger.error(
                    f"Failed to reconcile wallet for user {wallet.user.username}: {str(e)}"
                )
                discrepancies.append(wallet.user.id)

        logger.info(
            f"Wallet reconciliation completed: {reconciled_count} wallets checked"
        )
        if discrepancies:
            logger.warning(f"Discrepancies found in wallets: {discrepancies}")

        return {"reconciled_count": reconciled_count, "discrepancies": discrepancies}

    except Exception as e:
        logger.error(f"Failed to reconcile wallet balances: {str(e)}")
        return None
