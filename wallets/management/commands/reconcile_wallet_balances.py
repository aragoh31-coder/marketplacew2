from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
from wallets.models import Wallet, Transaction, WalletBalanceCheck
from wallets.utils import send_discrepancy_alert
import logging

logger = logging.getLogger('wallet.management')


class Command(BaseCommand):
    help = 'Reconcile wallet balances with transaction history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wallet-id',
            type=int,
            help='Reconcile specific wallet ID only',
        )
        parser.add_argument(
            '--fix-discrepancies',
            action='store_true',
            help='Automatically fix minor discrepancies',
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting wallet balance reconciliation...")
        
        if options['wallet_id']:
            wallets = Wallet.objects.filter(id=options['wallet_id'])
        else:
            wallets = Wallet.objects.all()
        
        discrepancies_found = 0
        wallets_checked = 0
        
        for wallet in wallets:
            try:
                wallets_checked += 1
                self.stdout.write(f"Checking wallet {wallet.id} for user {wallet.user.username}")
                
                btc_transactions = Transaction.objects.filter(
                    user=wallet.user,
                    currency='btc'
                ).aggregate(
                    deposits=Sum('amount', filter=Q(type__in=['deposit', 'conversion'])),
                    withdrawals=Sum('amount', filter=Q(type__in=['withdrawal', 'fee'])),
                    escrow_locks=Sum('amount', filter=Q(type='escrow_lock')),
                    escrow_releases=Sum('amount', filter=Q(type='escrow_release'))
                )
                
                xmr_transactions = Transaction.objects.filter(
                    user=wallet.user,
                    currency='xmr'
                ).aggregate(
                    deposits=Sum('amount', filter=Q(type__in=['deposit', 'conversion'])),
                    withdrawals=Sum('amount', filter=Q(type__in=['withdrawal', 'fee'])),
                    escrow_locks=Sum('amount', filter=Q(type='escrow_lock')),
                    escrow_releases=Sum('amount', filter=Q(type='escrow_release'))
                )
                
                expected_btc = (
                    (btc_transactions['deposits'] or Decimal('0')) -
                    (btc_transactions['withdrawals'] or Decimal('0'))
                )
                expected_xmr = (
                    (xmr_transactions['deposits'] or Decimal('0')) -
                    (xmr_transactions['withdrawals'] or Decimal('0'))
                )
                
                expected_escrow_btc = (
                    (btc_transactions['escrow_locks'] or Decimal('0')) -
                    (btc_transactions['escrow_releases'] or Decimal('0'))
                )
                expected_escrow_xmr = (
                    (xmr_transactions['escrow_locks'] or Decimal('0')) -
                    (xmr_transactions['escrow_releases'] or Decimal('0'))
                )
                
                btc_diff = abs(wallet.balance_btc - expected_btc)
                xmr_diff = abs(wallet.balance_xmr - expected_xmr)
                escrow_btc_diff = abs(wallet.escrow_btc - expected_escrow_btc)
                escrow_xmr_diff = abs(wallet.escrow_xmr - expected_escrow_xmr)
                
                discrepancy_found = (
                    btc_diff > Decimal('0.00000001') or
                    xmr_diff > Decimal('0.000000000001') or
                    escrow_btc_diff > Decimal('0.00000001') or
                    escrow_xmr_diff > Decimal('0.000000000001')
                )
                
                if discrepancy_found:
                    discrepancies_found += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Discrepancy found in wallet {wallet.id}:"
                        )
                    )
                    self.stdout.write(f"  BTC: Expected {expected_btc}, Actual {wallet.balance_btc}, Diff {btc_diff}")
                    self.stdout.write(f"  XMR: Expected {expected_xmr}, Actual {wallet.balance_xmr}, Diff {xmr_diff}")
                    self.stdout.write(f"  Escrow BTC: Expected {expected_escrow_btc}, Actual {wallet.escrow_btc}, Diff {escrow_btc_diff}")
                    self.stdout.write(f"  Escrow XMR: Expected {expected_escrow_xmr}, Actual {wallet.escrow_xmr}, Diff {escrow_xmr_diff}")
                    
                    check = WalletBalanceCheck.objects.create(
                        wallet=wallet,
                        expected_btc=expected_btc,
                        expected_xmr=expected_xmr,
                        expected_escrow_btc=expected_escrow_btc,
                        expected_escrow_xmr=expected_escrow_xmr,
                        actual_btc=wallet.balance_btc,
                        actual_xmr=wallet.balance_xmr,
                        actual_escrow_btc=wallet.escrow_btc,
                        actual_escrow_xmr=wallet.escrow_xmr,
                        discrepancy_found=True,
                        discrepancy_details={
                            'btc_diff': str(btc_diff),
                            'xmr_diff': str(xmr_diff),
                            'escrow_btc_diff': str(escrow_btc_diff),
                            'escrow_xmr_diff': str(escrow_xmr_diff)
                        }
                    )
                    
                    if btc_diff > Decimal('0.001') or xmr_diff > Decimal('0.1'):
                        send_discrepancy_alert(wallet, check)
                        self.stdout.write(
                            self.style.ERROR(
                                f"Major discrepancy alert sent for wallet {wallet.id}"
                            )
                        )
                    
                    if options['fix_discrepancies']:
                        if btc_diff <= Decimal('0.00001') and xmr_diff <= Decimal('0.001'):
                            wallet.balance_btc = expected_btc
                            wallet.balance_xmr = expected_xmr
                            wallet.escrow_btc = expected_escrow_btc
                            wallet.escrow_xmr = expected_escrow_xmr
                            wallet.save()
                            
                            check.resolved = True
                            check.resolution_notes = "Auto-fixed minor discrepancy"
                            check.resolved_at = timezone.now()
                            check.save()
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Auto-fixed minor discrepancy in wallet {wallet.id}"
                                )
                            )
                else:
                    self.stdout.write(f"  ✓ Wallet {wallet.id} balances are correct")
            
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error checking wallet {wallet.id}: {str(e)}"
                    )
                )
                logger.error(f"Error reconciling wallet {wallet.id}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciliation complete. Checked {wallets_checked} wallets, "
                f"found {discrepancies_found} discrepancies."
            )
        )
