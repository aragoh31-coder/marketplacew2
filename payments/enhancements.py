from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from core.base_models import PrivacyModel
from config.security_config import SECRET_MANAGER
from decimal import Decimal
import uuid
import hashlib
import secrets
import requests
from datetime import timedelta

User = get_user_model()


class PaymentMixer(PrivacyModel):
    """Payment mixing/tumbling service integration"""
    
    MIXER_STATUS = [
        ('DISABLED', 'Mixing Disabled'),
        ('ENABLED', 'Mixing Enabled'),
        ('PROCESSING', 'Processing Mix'),
        ('COMPLETED', 'Mix Completed'),
        ('FAILED', 'Mix Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_mixes')
    
    # Configuration (admin configurable)
    mixing_enabled = models.BooleanField(default=False)
    mixing_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    min_mix_amount_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0.001)
    min_mix_amount_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0.1)
    
    # Transaction details
    input_address = models.CharField(max_length=255)
    output_addresses = models.JSONField(default=list)  # Multiple output addresses
    amount = models.DecimalField(max_digits=20, decimal_places=12)
    currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    mixing_fee = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    final_amount = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    status = models.CharField(max_length=20, choices=MIXER_STATUS, default='DISABLED')
    
    # Mixing service details
    mixer_service = models.CharField(max_length=50, blank=True)  # Which mixer service used
    mixer_tx_id = models.CharField(max_length=255, blank=True)  # Mixer's transaction ID
    
    # Timing
    delay_hours = models.IntegerField(default=0)  # Random delay for mixing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'started_at']),
        ]
    
    def calculate_mixing_fee(self):
        """Calculate mixing fee based on admin settings"""
        self.mixing_fee = self.amount * (self.mixing_fee_percentage / 100)
        self.final_amount = self.amount - self.mixing_fee
        return self.mixing_fee
    
    def initiate_mixing(self, num_output_addresses=3):
        """Initiate payment mixing process"""
        if not self.mixing_enabled:
            return False, "Mixing is disabled"
        
        # Check minimum amounts
        if self.currency == 'BTC' and self.amount < self.min_mix_amount_btc:
            return False, f"Minimum BTC amount is {self.min_mix_amount_btc}"
        elif self.currency == 'XMR' and self.amount < self.min_mix_amount_xmr:
            return False, f"Minimum XMR amount is {self.min_mix_amount_xmr}"
        
        # Generate multiple output addresses
        self.output_addresses = []
        for _ in range(num_output_addresses):
            self.output_addresses.append(self._generate_new_address())
        
        # Add random delay (0-24 hours)
        import random
        self.delay_hours = random.randint(0, 24)
        
        self.status = 'PROCESSING'
        self.started_at = timezone.now()
        self.calculate_mixing_fee()
        self.save()
        
        # Queue mixing job
        from wallets.tasks import process_payment_mixing
        process_payment_mixing.apply_async(
            args=[self.id],
            countdown=self.delay_hours * 3600
        )
        
        return True, "Mixing initiated"
    
    def _generate_new_address(self):
        """Generate new address for mixed funds"""
        # This would integrate with wallet RPC
        # Simplified for demonstration
        return secrets.token_urlsafe(34)


class MultipleDepositAddresses(PrivacyModel):
    """Multiple deposit addresses per user for privacy"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_addresses')
    wallet = models.ForeignKey('wallets.Wallet', on_delete=models.CASCADE, related_name='addresses')
    
    address = models.CharField(max_length=255, unique=True)
    currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    # Usage tracking
    times_used = models.IntegerField(default=0)
    total_received = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Rotation settings
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Labels for user organization
    label = models.CharField(max_length=50, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'currency', 'is_active']),
            models.Index(fields=['address']),
        ]
    
    def rotate_address(self):
        """Rotate to new address for privacy"""
        self.is_active = False
        self.save()
        
        # Generate new address
        new_address = MultipleDepositAddresses.objects.create(
            user=self.user,
            wallet=self.wallet,
            currency=self.currency,
            label=f"Rotated from {self.label}"
        )
        
        return new_address


class CoinSwapService(PrivacyModel):
    """Coin swap service for cross-chain exchanges"""
    
    SWAP_STATUS = [
        ('PENDING', 'Pending'),
        ('CONFIRMING', 'Confirming'),
        ('SWAPPING', 'Swapping'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coin_swaps')
    
    # Swap configuration (admin configurable)
    swap_enabled = models.BooleanField(default=True)
    swap_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    
    # Swap details
    from_currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    to_currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    from_amount = models.DecimalField(max_digits=20, decimal_places=12)
    to_amount = models.DecimalField(max_digits=20, decimal_places=12)
    
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=8)
    swap_fee = models.DecimalField(max_digits=20, decimal_places=12)
    
    # Addresses
    deposit_address = models.CharField(max_length=255)
    receive_address = models.CharField(max_length=255)
    
    status = models.CharField(max_length=20, choices=SWAP_STATUS, default='PENDING')
    
    # Transaction tracking
    deposit_tx = models.CharField(max_length=255, blank=True)
    swap_tx = models.CharField(max_length=255, blank=True)
    
    # Service details
    swap_service = models.CharField(max_length=50, blank=True)
    service_order_id = models.CharField(max_length=255, blank=True)
    
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def get_exchange_rate(self):
        """Get current exchange rate from configured service"""
        # This would call actual exchange APIs
        # Simplified for demonstration
        if self.from_currency == 'BTC' and self.to_currency == 'XMR':
            return Decimal('333.33')  # 1 BTC = 333.33 XMR
        elif self.from_currency == 'XMR' and self.to_currency == 'BTC':
            return Decimal('0.003')  # 1 XMR = 0.003 BTC
        return Decimal('1.0')
    
    def calculate_swap(self):
        """Calculate swap amounts and fees"""
        self.exchange_rate = self.get_exchange_rate()
        
        # Calculate fee
        self.swap_fee = self.from_amount * (self.swap_fee_percentage / 100)
        
        # Calculate output amount
        amount_after_fee = self.from_amount - self.swap_fee
        self.to_amount = amount_after_fee * self.exchange_rate
        
        return self.to_amount
    
    def initiate_swap(self):
        """Initiate coin swap"""
        if not self.swap_enabled:
            return False, "Swapping is disabled"
        
        self.calculate_swap()
        
        # Generate deposit address
        self.deposit_address = self._generate_swap_deposit_address()
        
        # Set expiry (2 hours)
        self.expires_at = timezone.now() + timedelta(hours=2)
        
        self.status = 'PENDING'
        self.save()
        
        return True, f"Send {self.from_amount} {self.from_currency} to {self.deposit_address}"
    
    def _generate_swap_deposit_address(self):
        """Generate address for swap deposit"""
        return secrets.token_urlsafe(34)


class LightningNetwork(PrivacyModel):
    """Lightning Network support for BTC"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lightning_channels')
    
    # Channel details
    channel_id = models.CharField(max_length=255, unique=True)
    node_pubkey = models.CharField(max_length=255)
    
    # Capacity
    local_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    remote_balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    
    # Invoice support
    can_receive = models.BooleanField(default=True)
    can_send = models.BooleanField(default=True)
    
    # Channel state
    is_active = models.BooleanField(default=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def create_invoice(self, amount_sats, memo=''):
        """Create Lightning invoice"""
        import secrets
        
        # This would integrate with Lightning node
        # Simplified for demonstration
        payment_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        invoice = f"lnbc{amount_sats}p{payment_hash[:20]}"
        
        return {
            'invoice': invoice,
            'payment_hash': payment_hash,
            'amount': amount_sats,
            'memo': memo,
            'expires_at': timezone.now() + timedelta(hours=1)
        }
    
    def pay_invoice(self, invoice):
        """Pay Lightning invoice"""
        # This would integrate with Lightning node
        # Simplified for demonstration
        return {
            'success': True,
            'payment_hash': hashlib.sha256(invoice.encode()).hexdigest(),
            'fee': 1  # 1 satoshi fee
        }


class PaymentRouting(PrivacyModel):
    """Payment routing through multiple addresses"""
    
    payment = models.ForeignKey('wallets.Transaction', on_delete=models.CASCADE, related_name='routing_hops')
    
    # Hop details
    hop_number = models.IntegerField()
    from_address = models.CharField(max_length=255)
    to_address = models.CharField(max_length=255)
    
    amount = models.DecimalField(max_digits=20, decimal_places=12)
    fee = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    # Transaction tracking
    tx_hash = models.CharField(max_length=255, blank=True)
    confirmed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['hop_number']
        unique_together = ['payment', 'hop_number']
    
    @classmethod
    def create_routing_path(cls, payment, num_hops=3):
        """Create multi-hop routing path"""
        hops = []
        
        for i in range(num_hops):
            hop = cls(
                payment=payment,
                hop_number=i + 1,
                from_address=secrets.token_urlsafe(34),
                to_address=secrets.token_urlsafe(34),
                amount=payment.amount * Decimal('0.99') ** i,  # Small fee per hop
                fee=payment.amount * Decimal('0.01')
            )
            hops.append(hop)
        
        cls.objects.bulk_create(hops)
        return hops