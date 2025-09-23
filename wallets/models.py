from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import hashlib
import json
import secrets
import logging
from django.core.cache import cache
from config.security_config import SECRET_MANAGER
from core.security.encryption import FIELD_ENCRYPTION
from contextlib import contextmanager

logger = logging.getLogger('wallets.security')


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
    
    @contextmanager
    def _atomic_balance_operation(self):
        """Context manager for atomic balance operations with row-level locking"""
        with transaction.atomic():
            locked_wallet = Wallet.objects.select_for_update().get(pk=self.pk)
            yield locked_wallet
    
    def get_available_balance(self, currency):
        """Get available balance (total - escrow) with atomic read"""
        with self._atomic_balance_operation() as wallet:
            if currency == 'btc':
                return wallet.balance_btc - wallet.escrow_btc
            elif currency == 'xmr':
                return wallet.balance_xmr - wallet.escrow_xmr
            raise ValueError(f"Invalid currency: {currency}")
    
    def can_withdraw(self, currency, amount):
        """Check if withdrawal is allowed with enhanced security checks and atomic operations"""
        with self._atomic_balance_operation() as wallet:
            available = wallet.balance_btc - wallet.escrow_btc if currency == 'btc' else wallet.balance_xmr - wallet.escrow_xmr
            if amount > available:
                logger.warning(f"Insufficient balance for user {self.user.id}: requested {amount}, available {available}")
                return False, "Insufficient balance"
        
        daily_total = self.get_daily_withdrawal_total(currency)
        limit = getattr(self, f'daily_withdrawal_limit_{currency}')
        
        if daily_total + amount > limit:
            logger.warning(f"Daily limit exceeded for user {self.user.id}: total would be {daily_total + amount}, limit {limit}")
            return False, f"Daily withdrawal limit exceeded. Limit: {limit}, Already withdrawn: {daily_total}"
        
        velocity_check = self.check_withdrawal_velocity()
        if velocity_check:
            logger.warning(f"Velocity limit exceeded for user {self.user.id}")
            return False, "Too many withdrawal attempts. Please try again later."
        
        risk_score = self._calculate_withdrawal_risk(currency, amount)
        if risk_score > 80:
            logger.warning(f"High risk withdrawal for user {self.user.id}: risk score {risk_score}")
            return False, "High risk transaction detected. Manual review required."
        
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
    
    def _calculate_withdrawal_risk(self, currency, amount):
        """Calculate risk score for withdrawal"""
        risk_score = 0
        
        if currency == 'btc' and amount > Decimal('0.1'):
            risk_score += 30
        elif currency == 'xmr' and amount > Decimal('10'):
            risk_score += 30
        
        recent_withdrawals = WithdrawalRequest.objects.filter(
            user=self.user,
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        if recent_withdrawals > 3:
            risk_score += 25
        
        account_age = timezone.now() - self.user.date_joined
        if account_age.days < 7:
            risk_score += 40
        elif account_age.days < 30:
            risk_score += 20
        
        return risk_score
    
    def atomic_balance_update(self, currency, amount, operation='add', escrow=False):
        """Atomically update balance with proper locking"""
        with self._atomic_balance_operation() as wallet:
            if currency == 'btc':
                field = 'escrow_btc' if escrow else 'balance_btc'
                current_value = getattr(wallet, field)
                
                if operation == 'add':
                    new_value = current_value + amount
                elif operation == 'subtract':
                    new_value = current_value - amount
                    if new_value < 0:
                        raise ValueError("Insufficient balance for operation")
                else:
                    raise ValueError("Operation must be 'add' or 'subtract'")
                
                setattr(wallet, field, new_value)
            
            elif currency == 'xmr':
                field = 'escrow_xmr' if escrow else 'balance_xmr'
                current_value = getattr(wallet, field)
                
                if operation == 'add':
                    new_value = current_value + amount
                elif operation == 'subtract':
                    new_value = current_value - amount
                    if new_value < 0:
                        raise ValueError("Insufficient balance for operation")
                else:
                    raise ValueError("Operation must be 'add' or 'subtract'")
                
                setattr(wallet, field, new_value)
            
            else:
                raise ValueError(f"Invalid currency: {currency}")
            
            wallet.save()
            
            AuditLog.create_secure_log(
                user=self.user,
                action=f'balance_{operation}',
                details={
                    'currency': currency,
                    'amount': str(amount),
                    'escrow': escrow,
                    'new_balance': str(new_value),
                    'operation_id': secrets.token_urlsafe(16)
                },
                risk_score=0
            )
    
    def generate_balance_hash(self):
        """Generate cryptographically secure hash of current balances for integrity checking"""
        nonce = secrets.token_urlsafe(16)
        timestamp = timezone.now().isoformat()
        data = f"{self.user.id}:{self.balance_btc}:{self.balance_xmr}:{self.escrow_btc}:{self.escrow_xmr}:{timestamp}:{nonce}"
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
    """Encrypted audit logging for all wallet operations with enhanced security"""
    RISK_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
    ]
    
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('registration', 'User Registration'),
        ('withdrawal_request', 'Withdrawal Request'),
        ('withdrawal_approved', 'Withdrawal Approved'),
        ('withdrawal_rejected', 'Withdrawal Rejected'),
        ('withdrawal_cancelled', 'Withdrawal Cancelled'),
        ('balance_add', 'Balance Addition'),
        ('balance_subtract', 'Balance Subtraction'),
        ('conversion', 'Currency Conversion'),
        ('settings_change', 'Settings Change'),
        ('security_alert', 'Security Alert'),
        ('admin_action', 'Admin Action'),
        ('pgp_key_add', 'PGP Key Added'),
        ('pgp_key_remove', 'PGP Key Removed'),
        ('two_fa_enable', '2FA Enabled'),
        ('two_fa_disable', '2FA Disabled'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=255, default='privacy_protected')
    user_agent = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)  # Encrypted JSON
    risk_score = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='LOW')
    integrity_hash = models.CharField(max_length=64, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['risk_level']),
            models.Index(fields=['integrity_hash']),
        ]
        ordering = ['-timestamp']
    
    def set_details(self, details_dict):
        """Encrypt and store details"""
        if details_dict:
            json_data = json.dumps(details_dict)
            self.details = FIELD_ENCRYPTION.encrypt(json_data)
            self.integrity_hash = self.generate_integrity_hash(details_dict)
    
    def get_details(self):
        """Decrypt and return details"""
        if not self.details:
            return {}
        
        try:
            decrypted = FIELD_ENCRYPTION.decrypt(self.details)
            if decrypted:
                return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt audit log details: {e}")
        
        return {}
    
    def generate_integrity_hash(self, details_dict):
        """Generate integrity hash for tamper detection"""
        data = f"{self.user.id}:{self.action}:{self.timestamp.isoformat()}:{json.dumps(details_dict, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_integrity(self):
        """Verify audit log hasn't been tampered with"""
        details = self.get_details()
        expected_hash = self.generate_integrity_hash(details)
        return SECRET_MANAGER.secure_compare(expected_hash, self.integrity_hash)
    
    def save(self, *args, **kwargs):
        if hasattr(self, '_details_to_encrypt'):
            self.set_details(self._details_to_encrypt)
            delattr(self, '_details_to_encrypt')
        
        if not self.risk_level:
            if self.risk_score >= 80:
                self.risk_level = 'CRITICAL'
            elif self.risk_score >= 60:
                self.risk_level = 'HIGH'
            elif self.risk_score >= 30:
                self.risk_level = 'MEDIUM'
            else:
                self.risk_level = 'LOW'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def create_secure_log(cls, user, action, details=None, risk_score=0, ip_address='privacy_protected', user_agent=''):
        """Create audit log with automatic encryption"""
        log = cls(
            user=user,
            action=action,
            risk_score=risk_score,
            ip_address=ip_address,
            user_agent=user_agent[:200]
        )
        
        if details:
            log._details_to_encrypt = details
        
        log.save()
        return log


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


class EncryptedWalletAddress(models.Model):
    """Store encrypted wallet addresses for enhanced privacy"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    currency = models.CharField(max_length=3, choices=[('btc', 'Bitcoin'), ('xmr', 'Monero')])
    encrypted_address = models.TextField()
    address_type = models.CharField(max_length=20, choices=[
        ('deposit', 'Deposit Address'),
        ('change', 'Change Address'),
        ('withdrawal', 'Withdrawal Address')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'currency', 'address_type']),
            models.Index(fields=['is_active']),
        ]
    
    def set_address(self, address):
        """Encrypt and store address"""
        self.encrypted_address = FIELD_ENCRYPTION.encrypt(address)
    
    def get_address(self):
        """Decrypt and return address"""
        return FIELD_ENCRYPTION.decrypt(self.encrypted_address)


class DepositAddress(models.Model):
    """Legacy model for deposit addresses - use EncryptedWalletAddress for new implementations"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposit_addresses')
    currency = models.CharField(max_length=10, choices=WithdrawalRequest.CURRENCY_CHOICES)
    address = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'currency']
        verbose_name = "Deposit Address"
        verbose_name_plural = "Deposit Addresses"

    def __str__(self):
        return f"{self.user.username}'s {self.currency.upper()} Deposit Address"
    
    def migrate_to_encrypted(self):
        """Migrate to encrypted address storage"""
        encrypted_addr = EncryptedWalletAddress(
            user=self.user,
            currency=self.currency,
            address_type='deposit'
        )
        encrypted_addr.set_address(self.address)
        encrypted_addr.save()
        return encrypted_addr
