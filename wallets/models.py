from decimal import Decimal

from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField, transaction
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    btc_balance = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    xmr_balance = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("0")
    )
    escrow_balance = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    daily_withdrawal_limit_btc = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("1")
    )
    daily_withdrawal_limit_xmr = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("10")
    )

    def __str__(self):
        return f"Wallet({self.user.username})"

    @transaction.atomic
    def lock_escrow(self, amount, currency):
        if getattr(self, f"{currency}_balance") < amount:
            raise ValueError("Insufficient funds")
        setattr(
            self, f"{currency}_balance", getattr(self, f"{currency}_balance") - amount
        )
        self.escrow_balance += amount
        self.save()
        WalletAuditLog.create_log(self.user, amount, currency, "escrow_lock")

    @transaction.atomic
    def release_escrow(self, amount, currency, recipient_wallet):
        if self.escrow_balance < amount:
            raise ValueError("Insufficient escrow balance")
        self.escrow_balance -= amount
        setattr(
            recipient_wallet,
            f"{currency}_balance",
            getattr(recipient_wallet, f"{currency}_balance") + amount,
        )
        recipient_wallet.save()
        self.save()
        WalletAuditLog.create_log(self.user, amount, currency, "escrow_release")


class WalletAuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=12)
    currency = models.CharField(max_length=10)
    action = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now)
    previous_balance = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("0")
    )
    new_balance = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("0")
    )

    @classmethod
    def create_log(cls, user, amount, currency, action):
        wallet = Wallet.objects.get(user=user)
        cls.objects.create(
            user=user,
            amount=amount,
            currency=currency,
            action=action,
            previous_balance=getattr(wallet, f"{currency}_balance"),
            new_balance=getattr(wallet, f"{currency}_balance"),
        )


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=12)
    currency = models.CharField(max_length=10)
    address = EncryptedCharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=(
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ),
        default="pending",
    )
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    tx_hash = EncryptedCharField(max_length=128, blank=True, null=True)


class VendorStats(models.Model):
    vendor = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_sales = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    total_orders = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0"))


class BroadcastMessage(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_broadcasts",
    )
    target_group = models.CharField(
        max_length=20, choices=(("all", "All Users"), ("vendors", "Vendors"))
    )
