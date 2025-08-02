from celery import shared_task
from django.utils import timezone
from .models import WithdrawalRequest
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_withdrawal(withdrawal_id):
    withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
    withdrawal.status = 'completed'
    withdrawal.processed_at = timezone.now()
    withdrawal.tx_hash = 'FAKE_TX_HASH'
    withdrawal.save()
    logger.info(f"Withdrawal {withdrawal.pk} completed")
