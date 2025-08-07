from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
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
    escrow_btc = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    escrow_xmr = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("0")
    )
    daily_withdrawal_limit_btc = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("1")
    )
    daily_withdrawal_limit_xmr = models.DecimalField(
        max_digits=18, decimal_places=12, default=Decimal("10")
    )
    
    withdrawal_pin = models.CharField(max_length=128, blank=True, null=True)
    two_fa_enabled = models.BooleanField(default=False)
    two_fa_secret = models.CharField(max_length=32, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet({self.user.username})"
    
    def get_available_balance(self, currency):
        """Get available balance (total - escrow)"""
        if currency == 'btc':
            return self.btc_balance - self.escrow_btc
        elif currency == 'xmr':
            return self.xmr_balance - self.escrow_xmr
        raise ValueError(f"Invalid currency: {currency}")
    
    def get_daily_withdrawal_total(self, currency):
        """Calculate total withdrawals for today"""
        today = timezone.now().date()
        total = WithdrawalRequest.objects.filter(
            user=self.user,
            currency=currency,
            status='completed',
            processed_at__date=today
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return total

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
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    CURRENCY_CHOICES = [
        ('btc', 'Bitcoin'),
        ('xmr', 'Monero'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=12)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES)
    address = EncryptedCharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    two_fa_verified = models.BooleanField(default=False)
    pin_verified = models.BooleanField(default=False)
    
    risk_score = models.IntegerField(default=0)
    risk_factors = models.JSONField(default=dict, blank=True)
    manual_review_required = models.BooleanField(default=False)
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_withdrawals'
    )
    
    user_note = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    tx_hash = EncryptedCharField(max_length=128, blank=True, null=True)
    
    def calculate_risk_score(self):
        """Calculate risk score for withdrawal"""
        score = 0
        factors = []
        
        if self.currency == 'btc' and self.amount > Decimal('0.1'):
            score += 20
            factors.append("Large BTC amount")
        elif self.currency == 'xmr' and self.amount > Decimal('10'):
            score += 20
            factors.append("Large XMR amount")
        
        previous_use = WithdrawalRequest.objects.filter(
            user=self.user,
            address=self.address,
            status='completed'
        ).exists()
        
        if not previous_use:
            score += 15
            factors.append("New withdrawal address")
        
        if self.user.date_joined > timezone.now() - timezone.timedelta(days=7):
            score += 30
            factors.append("New account")
        
        recent_count = WithdrawalRequest.objects.filter(
            user=self.user,
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        if recent_count > 3:
            score += 25
            factors.append(f"Multiple recent withdrawals ({recent_count})")
        
        self.risk_score = score
        self.risk_factors = factors
        self.manual_review_required = score >= 40
        
        return score


class VendorStats(models.Model):
    vendor = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_sales = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("0")
    )
    total_orders = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0"))


class Transaction(models.Model):
    """Comprehensive transaction log"""
    TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('conversion', 'Conversion'),
        ('escrow_lock', 'Escrow Lock'),
        ('escrow_release', 'Escrow Release'),
        ('escrow_refund', 'Escrow Refund'),
        ('fee', 'Fee'),
        ('adjustment', 'Adjustment'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    amount = models.DecimalField(max_digits=18, decimal_places=12)
    currency = models.CharField(max_length=3)
    
    converted_amount = models.DecimalField(
        max_digits=18, 
        decimal_places=12, 
        null=True, 
        blank=True
    )
    converted_currency = models.CharField(max_length=3, null=True, blank=True)
    conversion_rate = models.DecimalField(
        max_digits=20, 
        decimal_places=12, 
        null=True, 
        blank=True
    )
    
    balance_before = models.DecimalField(max_digits=18, decimal_places=12)
    balance_after = models.DecimalField(max_digits=18, decimal_places=12)
    
    reference = models.CharField(max_length=255, db_index=True)
    related_object_type = models.CharField(max_length=50, null=True, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    
    transaction_hash = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'type', 'created_at']),
            models.Index(fields=['reference']),
            models.Index(fields=['transaction_hash']),
        ]
        ordering = ['-created_at']
    
    def generate_hash(self):
        """Generate unique transaction hash"""
        import hashlib
        data = f"{self.user.id}:{self.type}:{self.amount}:{self.currency}:{self.created_at.isoformat()}:{self.reference}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def save(self, *args, **kwargs):
        if not self.transaction_hash:
            self.transaction_hash = self.generate_hash()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_type_display()} - {self.amount} {self.currency} by {self.user.username}"


class ConversionRate(models.Model):
    """Exchange rates with history tracking"""
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=12)
    
    source = models.CharField(max_length=50, default='manual')
    source_data = models.JSONField(default=dict, blank=True)
    
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
        unique_together = ['from_currency', 'to_currency', 'valid_from']
    
    @classmethod
    def get_current_rate(cls, from_currency, to_currency):
        """Get current active rate"""
        now = timezone.now()
        rate = cls.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency,
            is_active=True,
            valid_from__lte=now
        ).filter(
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now)
        ).order_by('-valid_from').first()
        
        return rate.rate if rate else None


class AuditLog(models.Model):
    """Comprehensive audit trail for all wallet operations"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('withdrawal_request', 'Withdrawal Request'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
        ('withdrawal_cancelled', 'Withdrawal Cancelled'),
        ('conversion', 'Currency Conversion'),
        ('settings_change', 'Settings Change'),
        ('security_alert', 'Security Alert'),
        ('admin_action', 'Admin Action'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    details = models.JSONField(default=dict)
    
    risk_score = models.IntegerField(default=0)
    flagged = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'action', 'created_at']),
            models.Index(fields=['flagged', 'risk_score']),
        ]
        ordering = ['-created_at']


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
