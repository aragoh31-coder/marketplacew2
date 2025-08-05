from decimal import Decimal

from django.core.management.base import BaseCommand

from wallets.models import ConversionRate


class Command(BaseCommand):
    help = "Create initial conversion rates for BTC/XMR"

    def handle(self, *args, **options):
        btc_to_xmr_rate, created = ConversionRate.objects.get_or_create(
            from_currency="btc",
            to_currency="xmr",
            defaults={
                "rate": Decimal("150.000000000000"),  # 1 BTC = 150 XMR (example rate)
                "source": "manual",
                "is_active": True,
            },
        )

        xmr_to_btc_rate, created = ConversionRate.objects.get_or_create(
            from_currency="xmr",
            to_currency="btc",
            defaults={
                "rate": Decimal("0.006666666667"),  # 1 XMR = 0.0067 BTC (example rate)
                "source": "manual",
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Successfully created conversion rates"))
