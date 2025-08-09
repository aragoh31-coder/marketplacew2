import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update Django settings with wallet security configuration"

    def handle(self, *args, **options):
        settings_file = os.path.join(settings.BASE_DIR, "marketplace", "settings.py")

        wallet_config = """

try:
    from wallets.settings import WALLET_SECURITY, WALLET_SESSION_TIMEOUT_MINUTES, WALLET_LOGGING
    
    import logging.config
    logging.config.dictConfig(WALLET_LOGGING)
    
    SESSION_COOKIE_AGE = WALLET_SESSION_TIMEOUT_MINUTES * 60
    
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
except ImportError:
    pass
"""

        try:
            with open(settings_file, "r") as f:
                content = f.read()

            if "WALLET_SECURITY" not in content:
                with open(settings_file, "a") as f:
                    f.write(wallet_config)
                self.stdout.write(
                    self.style.SUCCESS(
                        "Successfully added wallet security configuration to settings.py"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "Wallet security configuration already exists in settings.py"
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error updating settings.py: {str(e)}"))
