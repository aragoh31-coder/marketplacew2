from django.db import models
from django.contrib.auth import get_user_model
from core.base_models import PrivacyModel
from vendors.models import Vendor
import uuid

User = get_user_model()


class Category(PrivacyModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"


class Product(PrivacyModel):
    PRODUCT_TYPES = [
        ('GIFT_CARD', 'Gift Card'),
        ('DIGITAL', 'Digital Product'),
        ('PHYSICAL', 'Physical Product'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default='GIFT_CARD')
    price_btc = models.DecimalField(max_digits=20, decimal_places=8)
    price_xmr = models.DecimalField(max_digits=20, decimal_places=8)
    stock_quantity = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    steganography_data = models.TextField(blank=True, null=True)  # Encrypted field
    
    image_filename = models.CharField(max_length=255, blank=True)
    thumbnail_filename = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.vendor.vendor_name}"
    
    @property
    def image_url(self):
        """Get image URL based on storage backend"""
        if not self.image_filename:
            return None
        
        from django.conf import settings
        config = settings.IMAGE_UPLOAD_SETTINGS
        if config['STORAGE_BACKEND'] == 'remote':
            base_url = config['REMOTE_STORAGE_CONFIG']['PUBLIC_URL']
            return f"{base_url}/{self.image_filename}"
        else:
            return f"/secure-images/products/{self.image_filename}"
    
    @property
    def thumbnail_url(self):
        """Get thumbnail URL"""
        if not self.thumbnail_filename:
            return None
        
        from django.conf import settings
        config = settings.IMAGE_UPLOAD_SETTINGS
        if config['STORAGE_BACKEND'] == 'remote':
            base_url = config['REMOTE_STORAGE_CONFIG']['PUBLIC_URL']
            return f"{base_url}/{self.thumbnail_filename}"
        else:
            return f"/secure-images/products/{self.thumbnail_filename}"
    
    def delete(self, *args, **kwargs):
        """Override delete to remove images"""
        if self.image_filename or self.thumbnail_filename:
            from core.security.image_security import SecureImageProcessor
            processor = SecureImageProcessor()
            processor.delete_images(self.image_filename, self.thumbnail_filename)
        
        super().delete(*args, **kwargs)


class ProductImage(PrivacyModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Image for {self.product.name}"
