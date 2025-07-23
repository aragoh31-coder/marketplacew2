from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from wallets.models import Wallet
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Create wallets for users who do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Create wallet for specific user ID only',
        )

    def handle(self, *args, **options):
        if options['user_id']:
            users = User.objects.filter(id=options['user_id'])
        else:
            users = User.objects.all()
        
        created_count = 0
        
        for user in users:
            wallet, created = Wallet.objects.get_or_create(
                user=user,
                defaults={
                    'balance_btc': Decimal('0'),
                    'balance_xmr': Decimal('0'),
                    'escrow_btc': Decimal('0'),
                    'escrow_xmr': Decimal('0'),
                    'daily_withdrawal_limit_btc': Decimal('1.0'),
                    'daily_withdrawal_limit_xmr': Decimal('100.0'),
                    'two_fa_enabled': False,
                    'withdrawal_pin': None,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"Created wallet for user {user.username} (ID: {user.id})")
            else:
                self.stdout.write(f"Wallet already exists for user {user.username}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} new wallets"
            )
        )
