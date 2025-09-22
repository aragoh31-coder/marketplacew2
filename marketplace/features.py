from django.db import models
from django.contrib.auth import get_user_model  
from django.utils import timezone
from core.base_models import PrivacyModel
from config.security_config import SECRET_MANAGER
from decimal import Decimal
import uuid
import json
from datetime import timedelta

User = get_user_model()


class BulkListing(PrivacyModel):
    """Bulk product listing management for vendors"""
    
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='bulk_listings')
    
    # Import/Export
    csv_template = models.TextField(blank=True)  # CSV template for bulk upload
    last_import = models.DateTimeField(null=True, blank=True)
    last_export = models.DateTimeField(null=True, blank=True)
    
    # Bulk operations
    products_created = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    products_deleted = models.IntegerField(default=0)
    
    # Status
    processing = models.BooleanField(default=False)
    errors = models.JSONField(default=list)
    
    def process_csv_import(self, csv_data):
        """Process bulk CSV import"""
        import csv
        from io import StringIO
        from products.models import Product, Category
        
        errors = []
        created = 0
        updated = 0
        
        reader = csv.DictReader(StringIO(csv_data))
        
        for row in reader:
            try:
                # Get or create category
                category, _ = Category.objects.get_or_create(
                    name=row.get('category', 'Other')
                )
                
                # Create or update product
                product, is_new = Product.objects.update_or_create(
                    vendor=self.vendor,
                    name=row['name'],
                    defaults={
                        'description': row.get('description', ''),
                        'category': category,
                        'price_btc': Decimal(row.get('price_btc', '0')),
                        'price_xmr': Decimal(row.get('price_xmr', '0')),
                        'stock_quantity': int(row.get('stock', '0')),
                        'product_type': row.get('type', 'PHYSICAL'),
                    }
                )
                
                if is_new:
                    created += 1
                else:
                    updated += 1
                    
            except Exception as e:
                errors.append(f"Row error: {str(e)}")
        
        self.products_created = created
        self.products_updated = updated
        self.errors = errors
        self.last_import = timezone.now()
        self.save()
        
        return created, updated, errors
    
    def export_to_csv(self):
        """Export products to CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'name', 'description', 'category', 'price_btc', 
            'price_xmr', 'stock', 'type', 'is_available'
        ])
        
        # Write products
        for product in self.vendor.products.all():
            writer.writerow([
                product.name,
                product.description,
                product.category.name,
                str(product.price_btc),
                str(product.price_xmr),
                product.stock_quantity,
                product.product_type,
                product.is_available
            ])
        
        self.last_export = timezone.now()
        self.save()
        
        return output.getvalue()


class ProductBundle(PrivacyModel):
    """Product bundles with discounts"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='bundles')
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    
    # Bundle products
    products = models.ManyToManyField('products.Product', related_name='bundles')
    
    # Pricing
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    bundle_price_btc = models.DecimalField(max_digits=20, decimal_places=8)
    bundle_price_xmr = models.DecimalField(max_digits=20, decimal_places=12)
    
    # Availability
    is_active = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)
    
    # Time limits
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def calculate_bundle_price(self):
        """Calculate bundle price with discount"""
        total_btc = sum(p.price_btc for p in self.products.all())
        total_xmr = sum(p.price_xmr for p in self.products.all())
        
        discount_factor = Decimal('1') - (self.discount_percentage / Decimal('100'))
        
        self.bundle_price_btc = total_btc * discount_factor
        self.bundle_price_xmr = total_xmr * discount_factor
        
        return self.bundle_price_btc, self.bundle_price_xmr
    
    def check_availability(self):
        """Check if bundle is available"""
        if not self.is_active:
            return False
        
        # Check time validity
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        
        # Check stock
        for product in self.products.all():
            if product.stock_quantity <= 0:
                return False
        
        return True


class FlashSale(PrivacyModel):
    """Time-limited flash sales"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='flash_sales')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='flash_sales')
    
    # Sale details
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    sale_price_btc = models.DecimalField(max_digits=20, decimal_places=8)
    sale_price_xmr = models.DecimalField(max_digits=20, decimal_places=12)
    
    # Time limits
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    
    # Quantity limits
    max_quantity = models.IntegerField(default=0)  # 0 = unlimited
    sold_quantity = models.IntegerField(default=0)
    
    # Display
    featured = models.BooleanField(default=False)
    banner_text = models.CharField(max_length=100, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['starts_at', 'ends_at']),
            models.Index(fields=['featured', 'starts_at']),
        ]
    
    def is_active(self):
        """Check if flash sale is currently active"""
        now = timezone.now()
        
        if now < self.starts_at or now > self.ends_at:
            return False
        
        if self.max_quantity > 0 and self.sold_quantity >= self.max_quantity:
            return False
        
        return True
    
    def time_remaining(self):
        """Get time remaining for sale"""
        if not self.is_active():
            return timedelta(0)
        
        return self.ends_at - timezone.now()


class VendorStorefront(PrivacyModel):
    """Custom vendor storefronts"""
    
    vendor = models.OneToOneField('vendors.Vendor', on_delete=models.CASCADE, related_name='storefront')
    
    # Customization
    banner_text = models.CharField(max_length=200, blank=True)
    description = models.TextField(max_length=2000)
    
    # PGP signed message
    pgp_signed_description = models.TextField(blank=True)
    
    # Featured products
    featured_products = models.ManyToManyField('products.Product', related_name='featured_in_storefronts')
    
    # Categories order
    category_order = models.JSONField(default=list)  # Custom category ordering
    
    # Policies
    shipping_policy = models.TextField(blank=True)
    refund_policy = models.TextField(blank=True)
    terms_of_service = models.TextField(blank=True)
    
    # Stats display
    show_stats = models.BooleanField(default=True)
    show_ratings = models.BooleanField(default=True)
    show_sales_count = models.BooleanField(default=False)  # Privacy consideration
    
    # Theme
    color_scheme = models.CharField(max_length=20, default='default')
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor']),
        ]
    
    def get_featured_products(self, limit=6):
        """Get featured products for storefront"""
        return self.featured_products.filter(
            is_available=True
        )[:limit]


class FeaturedListing(PrivacyModel):
    """Paid featured listings/ad system"""
    
    FEATURE_TYPES = [
        ('HOME', 'Homepage Feature'),
        ('CATEGORY', 'Category Feature'),
        ('SEARCH', 'Search Result Boost'),
        ('BANNER', 'Banner Ad'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='featured_listings')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='featured_listings')
    
    feature_type = models.CharField(max_length=20, choices=FEATURE_TYPES)
    
    # Pricing (admin configurable)
    cost_per_day_btc = models.DecimalField(max_digits=20, decimal_places=8)
    cost_per_day_xmr = models.DecimalField(max_digits=20, decimal_places=12)
    
    # Duration
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    days_purchased = models.IntegerField()
    
    # Payment
    total_cost = models.DecimalField(max_digits=20, decimal_places=12)
    currency_paid = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')])
    payment_tx = models.CharField(max_length=255, blank=True)
    
    # Performance
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    # Admin controls
    admin_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['feature_type', 'starts_at', 'ends_at']),
            models.Index(fields=['vendor', 'is_active']),
        ]
    
    def calculate_cost(self):
        """Calculate total cost for featured listing"""
        if self.currency_paid == 'BTC':
            daily_cost = self.cost_per_day_btc
        else:
            daily_cost = self.cost_per_day_xmr
        
        self.total_cost = daily_cost * Decimal(self.days_purchased)
        return self.total_cost
    
    def is_currently_active(self):
        """Check if featured listing is currently active"""
        now = timezone.now()
        
        return (self.is_active and 
                self.admin_approved and
                self.starts_at <= now <= self.ends_at)
    
    def record_impression(self):
        """Record an impression"""
        self.impressions += 1
        self.save(update_fields=['impressions'])
    
    def record_click(self):
        """Record a click"""
        self.clicks += 1
        self.save(update_fields=['clicks'])


class ProductClone(models.Model):
    """Product cloning for similar items"""
    
    @classmethod
    def clone_product(cls, original_product, vendor, modifications=None):
        """Clone a product with modifications"""
        from products.models import Product
        
        # Create new product instance
        cloned = Product(
            vendor=vendor,
            name=f"{original_product.name} (Copy)",
            description=original_product.description,
            category=original_product.category,
            product_type=original_product.product_type,
            price_btc=original_product.price_btc,
            price_xmr=original_product.price_xmr,
            stock_quantity=0,  # Start with 0 stock for safety
            is_available=False  # Start as unavailable
        )
        
        # Apply modifications if provided
        if modifications:
            for field, value in modifications.items():
                if hasattr(cloned, field):
                    setattr(cloned, field, value)
        
        cloned.save()
        
        # Clone tags if they exist
        if hasattr(original_product, 'tags'):
            cloned.tags.set(original_product.tags.all())
        
        return cloned


class VendorVacationMode(models.Model):
    """Enhanced vacation mode with auto-disable listings"""
    
    @classmethod  
    def activate_vacation_mode(cls, vendor, return_date=None, message=""):
        """Activate vacation mode and disable listings"""
        from products.models import Product
        
        # Set vendor vacation fields
        vendor.vacation_mode = True
        vendor.vacation_message = message
        vendor.vacation_started = timezone.now()
        vendor.vacation_ends = return_date
        vendor.save()
        
        # Disable all listings
        disabled_count = Product.objects.filter(
            vendor=vendor,
            is_available=True
        ).update(
            is_available=False,
            _vacation_disabled=True  # Track which were disabled by vacation
        )
        
        # Create notification
        from vendors.models import VendorNotification
        VendorNotification.objects.create(
            vendor=vendor,
            title='Vacation Mode Activated',
            message=f'{disabled_count} listings have been disabled during vacation.',
            notification_type='system'
        )
        
        return disabled_count
    
    @classmethod
    def deactivate_vacation_mode(cls, vendor):
        """Deactivate vacation mode and re-enable listings"""
        from products.models import Product
        
        # Reactivate vendor
        vendor.vacation_mode = False
        vendor.vacation_message = ''
        vendor.vacation_started = None
        vendor.vacation_ends = None
        vendor.save()
        
        # Re-enable previously disabled listings
        enabled_count = Product.objects.filter(
            vendor=vendor,
            _vacation_disabled=True
        ).update(
            is_available=True,
            _vacation_disabled=False
        )
        
        return enabled_count