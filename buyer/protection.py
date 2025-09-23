from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
from config.security_config import SECRET_MANAGER
from decimal import Decimal
import uuid

User = get_user_model()


class BuyerStatsDashboard(PrivacyModel):
    """Comprehensive buyer statistics dashboard"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_stats')
    
    # Order statistics
    total_orders = models.IntegerField(default=0)
    completed_orders = models.IntegerField(default=0)
    disputed_orders = models.IntegerField(default=0)
    refunded_orders = models.IntegerField(default=0)
    
    # Financial statistics
    total_spent_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_spent_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    total_saved_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)  # From discounts
    total_saved_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    # Time statistics
    average_delivery_days = models.FloatField(default=0)
    fastest_delivery_days = models.IntegerField(default=0)
    
    # Vendor statistics
    unique_vendors_purchased = models.IntegerField(default=0)
    favorite_vendor = models.ForeignKey('vendors.Vendor', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Product statistics
    products_purchased = models.IntegerField(default=0)
    favorite_category = models.ForeignKey('products.Category', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Review statistics
    reviews_written = models.IntegerField(default=0)
    helpful_votes_received = models.IntegerField(default=0)
    
    # Security statistics
    successful_transactions = models.IntegerField(default=0)
    fe_transactions = models.IntegerField(default=0)  # Finalize Early
    escrow_releases = models.IntegerField(default=0)
    
    # Loyalty metrics
    member_since = models.DateTimeField(default=timezone.now)
    loyalty_points = models.IntegerField(default=0)
    loyalty_tier = models.CharField(max_length=20, default='BRONZE')
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def update_statistics(self):
        """Update all buyer statistics"""
        from orders.models import Order, OrderItem
        from reviews.models import ProductReview
        
        # Update order statistics
        orders = Order.objects.filter(user=self.user)
        self.total_orders = orders.count()
        self.completed_orders = orders.filter(status='DELIVERED').count()
        self.disputed_orders = orders.filter(status='DISPUTED').count()
        self.refunded_orders = orders.filter(status='REFUNDED').count()
        
        # Update financial statistics
        completed = orders.filter(status='DELIVERED')
        self.total_spent_btc = sum(o.total_btc for o in completed)
        self.total_spent_xmr = sum(o.total_xmr for o in completed)
        
        # Update vendor statistics
        self.unique_vendors_purchased = orders.values('vendor').distinct().count()
        
        # Find favorite vendor (most orders from)
        vendor_counts = orders.values('vendor').annotate(
            count=models.Count('vendor')
        ).order_by('-count')
        
        if vendor_counts:
            from vendors.models import Vendor
            self.favorite_vendor = Vendor.objects.get(id=vendor_counts[0]['vendor'])
        
        # Update product statistics
        self.products_purchased = OrderItem.objects.filter(
            order__user=self.user,
            order__status='DELIVERED'
        ).count()
        
        # Update review statistics
        reviews = ProductReview.objects.filter(reviewer=self.user)
        self.reviews_written = reviews.count()
        self.helpful_votes_received = sum(r.helpful_votes for r in reviews)
        
        # Update loyalty tier
        self._calculate_loyalty_tier()
        
        self.last_updated = timezone.now()
        self.save()
    
    def _calculate_loyalty_tier(self):
        """Calculate buyer loyalty tier"""
        points = 0
        
        # Points for orders
        points += self.completed_orders * 10
        
        # Points for reviews
        points += self.reviews_written * 5
        points += self.helpful_votes_received * 2
        
        # Points for longevity
        days_member = (timezone.now() - self.member_since).days
        points += days_member // 30 * 5  # 5 points per month
        
        self.loyalty_points = points
        
        # Set tier
        if points >= 1000:
            self.loyalty_tier = 'PLATINUM'
        elif points >= 500:
            self.loyalty_tier = 'GOLD'
        elif points >= 200:
            self.loyalty_tier = 'SILVER'
        else:
            self.loyalty_tier = 'BRONZE'
    
    def get_statistics_summary(self):
        """Get formatted statistics summary"""
        return {
            'orders': {
                'total': self.total_orders,
                'completed': self.completed_orders,
                'success_rate': f"{(self.completed_orders / max(self.total_orders, 1)) * 100:.1f}%"
            },
            'spending': {
                'btc': str(self.total_spent_btc),
                'xmr': str(self.total_spent_xmr),
                'saved_btc': str(self.total_saved_btc),
                'saved_xmr': str(self.total_saved_xmr)
            },
            'loyalty': {
                'tier': self.loyalty_tier,
                'points': self.loyalty_points,
                'member_days': (timezone.now() - self.member_since).days
            }
        }


class FavoriteVendor(PrivacyModel):
    """Favorite vendors list for quick access"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_vendors')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='favorited_by')
    
    # Notes (encrypted)
    encrypted_notes = models.TextField(blank=True)
    
    # Statistics
    orders_placed = models.IntegerField(default=0)
    last_order_date = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    notify_new_products = models.BooleanField(default=False)
    notify_sales = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'vendor']
        indexes = [
            models.Index(fields=['user', 'vendor']),
        ]
    
    def set_notes(self, notes):
        """Set encrypted notes about vendor"""
        if notes:
            self.encrypted_notes = SECRET_MANAGER.encrypt_sensitive_data(notes)
    
    def get_notes(self):
        """Get decrypted notes"""
        if self.encrypted_notes:
            return SECRET_MANAGER.decrypt_sensitive_data(self.encrypted_notes)
        return ''


class ProductWatchlist(PrivacyModel):
    """Product watchlist with price alerts"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='watchers')
    
    # Price alerts
    alert_enabled = models.BooleanField(default=True)
    target_price_btc = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    target_price_xmr = models.DecimalField(max_digits=20, decimal_places=12, null=True, blank=True)
    
    # Stock alerts
    alert_on_restock = models.BooleanField(default=True)
    
    # Price tracking
    price_when_added_btc = models.DecimalField(max_digits=20, decimal_places=8)
    price_when_added_xmr = models.DecimalField(max_digits=20, decimal_places=12)
    
    # Alert history
    last_alert_sent = models.DateTimeField(null=True, blank=True)
    alerts_sent_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'product']
        indexes = [
            models.Index(fields=['user', 'alert_enabled']),
            models.Index(fields=['product', 'alert_enabled']),
        ]
    
    def check_price_alert(self):
        """Check if price alert should be triggered"""
        if not self.alert_enabled:
            return False
        
        # Check BTC price
        if self.target_price_btc and self.product.price_btc <= self.target_price_btc:
            return True, f"Price dropped to {self.product.price_btc} BTC"
        
        # Check XMR price
        if self.target_price_xmr and self.product.price_xmr <= self.target_price_xmr:
            return True, f"Price dropped to {self.product.price_xmr} XMR"
        
        return False, None
    
    def check_stock_alert(self):
        """Check if stock alert should be triggered"""
        if not self.alert_on_restock:
            return False
        
        if self.product.stock_quantity > 0:
            return True, f"{self.product.name} is back in stock"
        
        return False, None


class BuyerProtectionFund(PrivacyModel):
    """Insurance fund for buyer protection"""
    
    CLAIM_STATUS = [
        ('PENDING', 'Pending Review'),
        ('INVESTIGATING', 'Under Investigation'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid Out'),
        ('DENIED', 'Denied'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='protection_claims')
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='protection_claim')
    
    # Claim details
    claim_reason = models.TextField()
    claim_amount_btc = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    claim_amount_xmr = models.DecimalField(max_digits=20, decimal_places=12, null=True, blank=True)
    
    # Evidence
    evidence = models.TextField()  # Encrypted
    evidence_files = models.JSONField(default=list)  # Encrypted file references
    
    # Investigation
    investigator = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='investigated_claims')
    investigation_notes = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='PENDING')
    
    # Payout
    approved_amount_btc = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    approved_amount_xmr = models.DecimalField(max_digits=20, decimal_places=12, null=True, blank=True)
    payout_tx = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['status', 'submitted_at']),
        ]
    
    def calculate_coverage(self):
        """Calculate coverage amount based on fund rules"""
        # Basic coverage: 80% of order value up to maximum
        max_coverage_btc = Decimal('0.1')  # 0.1 BTC max
        max_coverage_xmr = Decimal('10')   # 10 XMR max
        
        if self.order.total_btc > 0:
            coverage = min(self.order.total_btc * Decimal('0.8'), max_coverage_btc)
            self.approved_amount_btc = coverage
        
        if self.order.total_xmr > 0:
            coverage = min(self.order.total_xmr * Decimal('0.8'), max_coverage_xmr)
            self.approved_amount_xmr = coverage
        
        return self.approved_amount_btc, self.approved_amount_xmr


class TestPurchaseSystem(PrivacyModel):
    """Test purchase system for new vendors"""
    
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='test_purchases')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_purchases')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Test purchase details
    test_amount = models.DecimalField(max_digits=20, decimal_places=12)
    currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    
    # Verification
    purchase_verified = models.BooleanField(default=False)
    quality_rating = models.IntegerField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Outcome
    passed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['vendor', 'buyer']
        indexes = [
            models.Index(fields=['vendor', 'passed']),
        ]
    
    def verify_test_purchase(self, rating, notes=''):
        """Verify test purchase quality"""
        self.purchase_verified = True
        self.quality_rating = rating
        self.verification_notes = notes
        
        # Pass if rating is 4 or higher
        self.passed = rating >= 4
        
        self.save()
        
        # Update vendor verification status
        if self.passed:
            vendor_tier = self.vendor.tier
            if vendor_tier:
                vendor_tier.stock_verified = True
                vendor_tier.verification_date = timezone.now()
                vendor_tier.save()


class VendorBlacklist(PrivacyModel):
    """Personal vendor blacklist"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blacklisted_vendors')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='blacklisted_by')
    
    reason = models.TextField()
    
    # Block settings
    hide_products = models.BooleanField(default=True)
    block_messages = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'vendor']
        indexes = [
            models.Index(fields=['user', 'vendor']),
        ]


class AutoPurchaseAlert(PrivacyModel):
    """Automated purchase alerts for specific criteria"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auto_purchase_alerts')
    
    # Alert criteria
    category = models.ForeignKey('products.Category', null=True, blank=True, on_delete=models.CASCADE)
    vendor = models.ForeignKey('vendors.Vendor', null=True, blank=True, on_delete=models.CASCADE)
    keywords = models.TextField(blank=True)  # Comma-separated keywords
    
    # Price criteria
    max_price_btc = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    max_price_xmr = models.DecimalField(max_digits=20, decimal_places=12, null=True, blank=True)
    
    # Settings
    is_active = models.BooleanField(default=True)
    check_frequency_hours = models.IntegerField(default=24)
    
    # Last check
    last_checked = models.DateTimeField(null=True, blank=True)
    matches_found = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active', 'last_checked']),
        ]
    
    def check_for_matches(self):
        """Check for products matching criteria"""
        from products.models import Product
        
        queryset = Product.objects.filter(is_available=True)
        
        if self.category:
            queryset = queryset.filter(category=self.category)
        
        if self.vendor:
            queryset = queryset.filter(vendor=self.vendor)
        
        if self.keywords:
            keywords_list = [k.strip() for k in self.keywords.split(',')]
            for keyword in keywords_list:
                queryset = queryset.filter(
                    models.Q(name__icontains=keyword) |
                    models.Q(description__icontains=keyword)
                )
        
        if self.max_price_btc:
            queryset = queryset.filter(price_btc__lte=self.max_price_btc)
        
        if self.max_price_xmr:
            queryset = queryset.filter(price_xmr__lte=self.max_price_xmr)
        
        self.last_checked = timezone.now()
        self.matches_found = queryset.count()
        self.save()
        
        return queryset