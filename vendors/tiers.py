from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
from decimal import Decimal
import uuid

User = get_user_model()


class VendorTier(PrivacyModel):
    """Tiered vendor levels with graduated requirements"""
    
    TIER_LEVELS = [
        ('STARTER', 'Starter Vendor'),
        ('ESTABLISHED', 'Established Vendor'),
        ('TRUSTED', 'Trusted Vendor'),
        ('PREMIUM', 'Premium Vendor'),
        ('ELITE', 'Elite Vendor'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.OneToOneField('vendors.Vendor', on_delete=models.CASCADE, related_name='tier')
    
    current_tier = models.CharField(max_length=20, choices=TIER_LEVELS, default='STARTER')
    
    # Requirements tracking
    total_sales = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    completed_orders = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    dispute_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Bond requirements (in USD equivalent)
    bond_required = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    bond_paid_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    bond_currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    # Tier benefits
    fe_enabled = models.BooleanField(default=False)  # Finalize Early
    reduced_fees = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Fee reduction %
    featured_listings = models.IntegerField(default=0)  # Number of featured slots
    bulk_listing_enabled = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    custom_storefront = models.BooleanField(default=False)
    
    # Trust badges
    badges = models.JSONField(default=list)  # List of earned badges
    
    # Verification
    identity_verified = models.BooleanField(default=False)
    stock_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    
    # Milestone tracking
    next_tier = models.CharField(max_length=20, blank=True)
    progress_to_next = models.IntegerField(default=0)  # Percentage
    
    # Forfeiture tracking
    bond_forfeited = models.BooleanField(default=False)
    forfeiture_reason = models.TextField(blank=True)
    forfeiture_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor', 'current_tier']),
            models.Index(fields=['fe_enabled']),
        ]
    
    def calculate_tier(self):
        """Calculate vendor tier based on performance metrics"""
        
        # Tier requirements
        tier_requirements = {
            'STARTER': {
                'orders': 0,
                'sales': 0,
                'rating': 0,
                'bond': 500,
                'max_dispute_rate': 100
            },
            'ESTABLISHED': {
                'orders': 10,
                'sales': 1000,
                'rating': 4.0,
                'bond': 1000,
                'max_dispute_rate': 10
            },
            'TRUSTED': {
                'orders': 50,
                'sales': 10000,
                'rating': 4.3,
                'bond': 2000,
                'max_dispute_rate': 5
            },
            'PREMIUM': {
                'orders': 200,
                'sales': 50000,
                'rating': 4.5,
                'bond': 5000,
                'max_dispute_rate': 3
            },
            'ELITE': {
                'orders': 500,
                'sales': 100000,
                'rating': 4.7,
                'bond': 10000,
                'max_dispute_rate': 2
            }
        }
        
        # Check each tier from highest to lowest
        for tier in ['ELITE', 'PREMIUM', 'TRUSTED', 'ESTABLISHED', 'STARTER']:
            req = tier_requirements[tier]
            
            if (self.completed_orders >= req['orders'] and
                self.total_sales >= req['sales'] and
                self.average_rating >= req['rating'] and
                self.dispute_rate <= req['max_dispute_rate'] and
                self.bond_paid_amount >= self._convert_to_crypto(req['bond'])):
                
                if self.current_tier != tier:
                    self._upgrade_tier(tier)
                break
        
        # Calculate progress to next tier
        self._calculate_progress()
    
    def _upgrade_tier(self, new_tier):
        """Upgrade vendor to new tier with benefits"""
        old_tier = self.current_tier
        self.current_tier = new_tier
        
        # Apply tier benefits
        tier_benefits = {
            'STARTER': {
                'fe_enabled': False,
                'reduced_fees': 0,
                'featured_listings': 0,
                'bulk_listing': False,
                'priority_support': False,
                'custom_storefront': False
            },
            'ESTABLISHED': {
                'fe_enabled': False,
                'reduced_fees': 5,
                'featured_listings': 1,
                'bulk_listing': True,
                'priority_support': False,
                'custom_storefront': False
            },
            'TRUSTED': {
                'fe_enabled': True,
                'reduced_fees': 10,
                'featured_listings': 3,
                'bulk_listing': True,
                'priority_support': True,
                'custom_storefront': False
            },
            'PREMIUM': {
                'fe_enabled': True,
                'reduced_fees': 15,
                'featured_listings': 5,
                'bulk_listing': True,
                'priority_support': True,
                'custom_storefront': True
            },
            'ELITE': {
                'fe_enabled': True,
                'reduced_fees': 20,
                'featured_listings': 10,
                'bulk_listing': True,
                'priority_support': True,
                'custom_storefront': True
            }
        }
        
        benefits = tier_benefits[new_tier]
        self.fe_enabled = benefits['fe_enabled']
        self.reduced_fees = benefits['reduced_fees']
        self.featured_listings = benefits['featured_listings']
        self.bulk_listing_enabled = benefits['bulk_listing']
        self.priority_support = benefits['priority_support']
        self.custom_storefront = benefits['custom_storefront']
        
        # Add badge
        badge = f"tier_upgrade_{new_tier.lower()}_{timezone.now().date()}"
        if badge not in self.badges:
            self.badges.append(badge)
        
        self.save()
        
        # Create notification
        self._notify_tier_change(old_tier, new_tier)
    
    def _calculate_progress(self):
        """Calculate progress to next tier"""
        tier_order = ['STARTER', 'ESTABLISHED', 'TRUSTED', 'PREMIUM', 'ELITE']
        current_index = tier_order.index(self.current_tier)
        
        if current_index < len(tier_order) - 1:
            self.next_tier = tier_order[current_index + 1]
            # Calculate percentage progress (simplified)
            # Would need actual requirements comparison
            self.progress_to_next = min(75, int((self.completed_orders / 10) * 10))
        else:
            self.next_tier = ''
            self.progress_to_next = 100
    
    def verify_vendor(self, verification_type='identity'):
        """Verify vendor identity or stock"""
        if verification_type == 'identity':
            self.identity_verified = True
            self.badges.append(f"identity_verified_{timezone.now().date()}")
        elif verification_type == 'stock':
            self.stock_verified = True
            self.badges.append(f"stock_verified_{timezone.now().date()}")
        
        self.verification_date = timezone.now()
        self.save()
    
    def forfeit_bond(self, reason):
        """Forfeit vendor bond for violations"""
        self.bond_forfeited = True
        self.forfeiture_reason = reason
        self.forfeiture_date = timezone.now()
        self.fe_enabled = False  # Revoke FE privileges
        self.current_tier = 'STARTER'  # Reset to starter
        self.save()
        
        # Create security alert
        from apps.security.models import SecurityAlert
        SecurityAlert.objects.create(
            alert_type='BOND_FORFEITURE',
            severity='HIGH',
            vendor=self.vendor,
            details={'reason': reason, 'amount': str(self.bond_paid_amount)}
        )
    
    def award_milestone(self, milestone_type):
        """Award milestone badges"""
        milestone_badges = {
            'first_sale': 'first_sale_completed',
            '10_sales': 'sales_milestone_10',
            '100_sales': 'sales_milestone_100',
            '1000_sales': 'sales_milestone_1000',
            'perfect_rating': 'perfect_5_star_rating',
            'quick_shipper': 'fast_shipping_award',
            'high_volume': 'high_volume_seller',
        }
        
        if milestone_type in milestone_badges:
            badge = milestone_badges[milestone_type]
            if badge not in self.badges:
                self.badges.append(badge)
                self.save()
    
    def _convert_to_crypto(self, usd_amount):
        """Convert USD bond amount to crypto"""
        # This would integrate with real exchange rates
        # Simplified for demonstration
        if self.bond_currency == 'BTC':
            return Decimal(usd_amount) / Decimal('50000')  # Assuming $50k/BTC
        else:  # XMR
            return Decimal(usd_amount) / Decimal('150')  # Assuming $150/XMR
    
    def _notify_tier_change(self, old_tier, new_tier):
        """Send notification about tier change"""
        from vendors.models import VendorNotification
        
        VendorNotification.objects.create(
            vendor=self.vendor,
            title=f'Tier Upgrade: {new_tier}',
            message=f'Congratulations! You have been upgraded from {old_tier} to {new_tier}. New benefits have been activated.',
            notification_type='system'
        )


class VendorVerification(PrivacyModel):
    """Vendor verification process tracking"""
    
    VERIFICATION_TYPES = [
        ('identity', 'Identity Verification'),
        ('stock', 'Stock Verification'),
        ('business', 'Business Verification'),
    ]
    
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='verifications')
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPES)
    
    # Proof submission
    proof_submitted = models.TextField()  # Encrypted
    proof_hash = models.CharField(max_length=64)
    
    # Verification status
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['vendor', 'verification_type']
        ordering = ['-created_at']