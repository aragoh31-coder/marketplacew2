from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import hashlib
import json
from django.core.cache import cache


class Wallet(models.Model):
    """Secure wallet implementation with proper decimal handling"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    
    balance_btc = models.DecimalField(
        max_digits=16, 
        decimal_places=8, 
        default=Decimal('0.00000000'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    balance_xmr = models.DecimalField(
        max_digits=16, 
        decimal_places=12, 
        default=Decimal('0.000000000000'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    escrow_btc = models.DecimalField(
        max_digits=16, 
        decimal_places=8, 
        default=Decimal('0.00000000'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    escrow_xmr = models.DecimalField(
        max_digits=16, 
        decimal_places=12, 
        default=Decimal('0.000000000000'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    withdrawal_pin = models.CharField(max_length=128, blank=True, null=True)  # Hashed PIN
    two_fa_enabled = models.BooleanField(default=False)
    two_fa_secret = models.CharField(max_length=32, blank=True, null=True)
    
    daily_withdrawal_limit_btc = models.DecimalField(
        max_digits=16, 
        decimal_places=8, 
        default=Decimal('1.00000000')
    )
    daily_withdrawal_limit_xmr = models.DecimalField(
        max_digits=16, 
        decimal_places=12, 
        default=Decimal('100.000000000000')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'updated_at']),
        ]
    
    def get_available_balance(self, currency):
        """Get available balance (total - escrow)"""
        if currency == 'btc':
            return self.balance_btc - self.escrow_btc
        elif currency == 'xmr':
            return self.balance_xmr - self.escrow_xmr
        raise ValueError(f"Invalid currency: {currency}")
    
    def can_withdraw(self, currency, amount):
        """Check if withdrawal is allowed with all security checks"""
        available = self.get_available_balance(currency)
        if amount > available:
            return False, "Insufficient balance"
        
        daily_total = self.get_daily_withdrawal_total(currency)
        limit = getattr(self, f'daily_withdrawal_limit_{currency}')
        
        if daily_total + amount > limit:
            return False, f"Daily withdrawal limit exceeded. Limit: {limit}, Already withdrawn: {daily_total}"
        
        if self.check_withdrawal_velocity():
            return False, "Too many withdrawal attempts. Please try again later."
        
        return True, "OK"
    
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
    
    def check_withdrawal_velocity(self):
        """Check for suspicious withdrawal patterns"""
        cache_key = f'withdrawal_velocity:{self.user.id}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:  # Max 5 withdrawals per hour
            return True
            
        cache.set(cache_key, attempts + 1, 3600)  # 1 hour expiry
        return False
    
    def generate_balance_hash(self):
        """Generate hash of current balances for integrity checking"""
        data = f"{self.user.id}:{self.balance_btc}:{self.balance_xmr}:{self.escrow_btc}:{self.escrow_xmr}:{self.updated_at.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()


class WithdrawalRequest(models.Model):
    """Secure withdrawal request with comprehensive tracking"""
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
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(
        max_digits=16, 
        decimal_places=12,
        validators=[MinValueValidator(Decimal('0.000000000001'))]
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    address = models.CharField(max_length=255)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_withdrawals'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    tx_hash = models.CharField(max_length=255, blank=True, null=True)
    tx_fee = models.DecimalField(
        max_digits=16, 
        decimal_places=12, 
        null=True, 
        blank=True
    )
    
    two_fa_verified = models.BooleanField(default=False)
    pin_verified = models.BooleanField(default=False)
    
    risk_score = models.IntegerField(default=0)
    risk_factors = models.JSONField(default=dict, blank=True)
    manual_review_required = models.BooleanField(default=False)
    
    user_note = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['status', 'manual_review_required']),
        ]
        ordering = ['-created_at']
    
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
    
    amount = models.DecimalField(max_digits=16, decimal_places=12)
    currency = models.CharField(max_length=3)
    
    converted_amount = models.DecimalField(
        max_digits=16, 
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
    
    balance_before = models.DecimalField(max_digits=16, decimal_places=12)
    balance_after = models.DecimalField(max_digits=16, decimal_places=12)
    
    reference = models.CharField(max_length=255, db_index=True)
    related_object_type = models.CharField(max_length=50, null=True, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    
    transaction_hash = models.CharField(max_length=64, unique=True)
    
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
        data = f"{self.user.id}:{self.type}:{self.amount}:{self.currency}:{self.created_at.isoformat()}:{self.reference}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def save(self, *args, **kwargs):
        if not self.transaction_hash:
            self.transaction_hash = self.generate_hash()
        super().save(*args, **kwargs)


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


class WalletBalanceCheck(models.Model):
    """Periodic balance reconciliation for integrity checking"""
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    
    expected_btc = models.DecimalField(max_digits=16, decimal_places=8)
    expected_xmr = models.DecimalField(max_digits=16, decimal_places=12)
    expected_escrow_btc = models.DecimalField(max_digits=16, decimal_places=8)
    expected_escrow_xmr = models.DecimalField(max_digits=16, decimal_places=12)
    
    actual_btc = models.DecimalField(max_digits=16, decimal_places=8)
    actual_xmr = models.DecimalField(max_digits=16, decimal_places=12)
    actual_escrow_btc = models.DecimalField(max_digits=16, decimal_places=8)
    actual_escrow_xmr = models.DecimalField(max_digits=16, decimal_places=12)
    
    discrepancy_found = models.BooleanField(default=False)
    discrepancy_details = models.JSONField(default=dict, blank=True)
    
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    resolution_notes = models.TextField(blank=True)
    
    checked_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['discrepancy_found', 'resolved', 'checked_at']),
        ]
