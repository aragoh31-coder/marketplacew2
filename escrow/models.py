from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
import uuid
from datetime import timedelta
import hashlib

User = get_user_model()


class AdvancedEscrow(PrivacyModel):
    """Advanced escrow system with FE, auto-finalize, and partial release"""
    
    ESCROW_STATUS = [
        ('PENDING', 'Pending Payment'),
        ('FUNDED', 'Funded'),
        ('RELEASED', 'Released to Vendor'),
        ('REFUNDED', 'Refunded to Buyer'),
        ('DISPUTED', 'Under Dispute'),
        ('PARTIAL_RELEASED', 'Partially Released'),
        ('AUTO_FINALIZED', 'Auto-Finalized'),
        ('FE_APPROVED', 'Finalize Early Approved'),
        ('EXPIRED', 'Expired'),
        ('EXTENDED', 'Extended'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='advanced_escrow')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_escrows')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='vendor_escrows')
    
    amount_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    amount_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    status = models.CharField(max_length=20, choices=ESCROW_STATUS, default='PENDING')
    
    # Finalize Early (FE) fields
    fe_enabled = models.BooleanField(default=False)
    fe_requested = models.BooleanField(default=False)
    fe_approved_at = models.DateTimeField(null=True, blank=True)
    fe_threshold_sales = models.IntegerField(default=50)  # Min sales for FE eligibility
    fe_threshold_rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.5)  # Min rating
    
    # Auto-finalize settings
    auto_finalize_enabled = models.BooleanField(default=True)
    auto_finalize_days = models.IntegerField(default=14)  # Configurable 14-30 days
    auto_finalize_date = models.DateTimeField(null=True, blank=True)
    
    # Extension handling
    extension_requested = models.BooleanField(default=False)
    extension_reason = models.TextField(blank=True)
    extension_days = models.IntegerField(default=0)
    extension_approved = models.BooleanField(default=False)
    original_finalize_date = models.DateTimeField(null=True, blank=True)
    
    # Partial release tracking
    total_released = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    partial_releases = models.JSONField(default=list)  # Track each partial release
    
    # Time-lock settings
    time_locked = models.BooleanField(default=False)
    time_lock_expires = models.DateTimeField(null=True, blank=True)
    
    # Dispute tracking
    dispute_count = models.IntegerField(default=0)
    dispute_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Escrow addresses
    escrow_address = models.CharField(max_length=255, unique=True)
    return_address = models.CharField(max_length=255, blank=True)  # For refunds
    
    # Transaction hashes
    funding_tx = models.CharField(max_length=255, blank=True)
    release_tx = models.CharField(max_length=255, blank=True)
    
    funded_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'auto_finalize_date']),
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['buyer', 'status']),
        ]
    
    def check_fe_eligibility(self):
        """Check if vendor is eligible for FE on this order"""
        if not self.vendor.bond_paid:
            return False, "Vendor bond not paid"
        
        completed_orders = self.vendor.vendor_escrows.filter(
            status__in=['RELEASED', 'AUTO_FINALIZED', 'FE_APPROVED']
        ).count()
        
        if completed_orders < self.fe_threshold_sales:
            return False, f"Insufficient sales history ({completed_orders}/{self.fe_threshold_sales})"
        
        if self.vendor.rating < self.fe_threshold_rating:
            return False, f"Rating too low ({self.vendor.rating}/{self.fe_threshold_rating})"
        
        dispute_rate = self.calculate_vendor_dispute_rate()
        if dispute_rate > 5.0:  # Max 5% dispute rate
            return False, f"Dispute rate too high ({dispute_rate}%)"
        
        return True, "FE eligible"
    
    def calculate_vendor_dispute_rate(self):
        """Calculate vendor's dispute percentage"""
        total = self.vendor.vendor_escrows.count()
        if total == 0:
            return 0
        disputed = self.vendor.vendor_escrows.filter(status='DISPUTED').count()
        return (disputed / total) * 100
    
    def request_extension(self, days, reason):
        """Request escrow extension for delayed shipment"""
        if self.status not in ['FUNDED', 'DISPUTED']:
            return False, "Extension only available for funded escrows"
        
        if days > 14:
            return False, "Maximum extension is 14 days"
        
        self.extension_requested = True
        self.extension_reason = reason
        self.extension_days = days
        self.save()
        
        return True, "Extension requested"
    
    def approve_extension(self):
        """Approve escrow extension"""
        if not self.extension_requested:
            return False, "No extension requested"
        
        self.original_finalize_date = self.auto_finalize_date
        self.auto_finalize_date += timedelta(days=self.extension_days)
        self.extension_approved = True
        self.status = 'EXTENDED'
        self.save()
        
        return True, f"Extended by {self.extension_days} days"
    
    def partial_release(self, amount, item_ids=None):
        """Release partial payment for multi-item orders"""
        if self.status != 'FUNDED':
            return False, "Escrow must be funded"
        
        if self.time_locked and timezone.now() < self.time_lock_expires:
            return False, f"Time-locked until {self.time_lock_expires}"
        
        currency_field = f'amount_{self.currency.lower()}'
        total_amount = getattr(self, currency_field)
        
        if amount > (total_amount - self.total_released):
            return False, "Insufficient funds for partial release"
        
        release_record = {
            'amount': str(amount),
            'timestamp': timezone.now().isoformat(),
            'items': item_ids or [],
            'hash': hashlib.sha256(f"{amount}{timezone.now()}".encode()).hexdigest()[:16]
        }
        
        self.partial_releases.append(release_record)
        self.total_released += amount
        
        if self.total_released >= total_amount:
            self.status = 'RELEASED'
            self.released_at = timezone.now()
        else:
            self.status = 'PARTIAL_RELEASED'
        
        self.save()
        return True, f"Released {amount} {self.currency}"
    
    def initiate_auto_finalize(self):
        """Set up auto-finalize timer when order is marked shipped"""
        if not self.auto_finalize_enabled:
            return
        
        self.auto_finalize_date = timezone.now() + timedelta(days=self.auto_finalize_days)
        self.save()
    
    def check_auto_finalize(self):
        """Check if escrow should be auto-finalized"""
        if not self.auto_finalize_enabled:
            return False
        
        if self.status != 'FUNDED':
            return False
        
        if timezone.now() >= self.auto_finalize_date:
            self.status = 'AUTO_FINALIZED'
            self.released_at = timezone.now()
            self.save()
            return True
        
        return False
    
    def enable_time_lock(self, hours=48):
        """Enable time-lock to prevent early release"""
        self.time_locked = True
        self.time_lock_expires = timezone.now() + timedelta(hours=hours)
        self.save()
    
    def __str__(self):
        return f"Escrow {self.id} - {self.status}"


class EscrowExtensionRequest(PrivacyModel):
    """Track escrow extension requests"""
    
    escrow = models.ForeignKey(AdvancedEscrow, on_delete=models.CASCADE, related_name='extension_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    days_requested = models.IntegerField()
    reason = models.TextField()
    
    approved = models.BooleanField(default=False)
    denied = models.BooleanField(default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_extensions')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']