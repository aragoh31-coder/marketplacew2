from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
from config.security_config import SECRET_MANAGER
from decimal import Decimal
import uuid
import hashlib
from datetime import timedelta

User = get_user_model()


class ShippingMethod(PrivacyModel):
    """Shipping methods with stealth options"""
    
    SHIPPING_TYPES = [
        ('REGULAR', 'Regular Mail'),
        ('EXPRESS', 'Express Shipping'),
        ('STEALTH', 'Stealth Packaging'),
        ('DEAD_DROP', 'Dead Drop'),
        ('DIGITAL', 'Digital Delivery'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='shipping_methods')
    
    name = models.CharField(max_length=100)
    shipping_type = models.CharField(max_length=20, choices=SHIPPING_TYPES, default='REGULAR')
    description = models.TextField()
    
    # Shipping details
    min_days = models.IntegerField(default=3)
    max_days = models.IntegerField(default=7)
    
    # Costs
    base_cost_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    base_cost_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    # Origin countries (encrypted)
    ships_from = models.TextField()  # Encrypted JSON list of countries
    ships_to = models.TextField()  # Encrypted JSON list of countries
    
    # Stealth options
    decoy_available = models.BooleanField(default=False)
    decoy_description = models.TextField(blank=True)
    vacuum_sealed = models.BooleanField(default=False)
    mylar_bags = models.BooleanField(default=False)
    visual_barrier = models.BooleanField(default=False)
    
    # Tracking
    tracking_available = models.BooleanField(default=False)
    encrypted_tracking = models.BooleanField(default=True)
    
    # Dead drop specific
    requires_coordinates = models.BooleanField(default=False)
    max_pickup_days = models.IntegerField(default=7)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor', 'shipping_type', 'is_active']),
        ]
    
    def encrypt_countries(self, countries_list):
        """Encrypt shipping countries for privacy"""
        import json
        data = json.dumps(countries_list)
        return SECRET_MANAGER.encrypt_sensitive_data(data)
    
    def decrypt_countries(self, encrypted_data):
        """Decrypt shipping countries"""
        import json
        if not encrypted_data:
            return []
        decrypted = SECRET_MANAGER.decrypt_sensitive_data(encrypted_data)
        return json.loads(decrypted)
    
    def calculate_shipping_cost(self, destination, weight=None):
        """Calculate shipping cost based on destination"""
        base_cost = self.base_cost_btc if self.base_cost_btc > 0 else self.base_cost_xmr
        
        # Add modifiers
        if self.shipping_type == 'EXPRESS':
            base_cost *= Decimal('1.5')
        elif self.shipping_type == 'STEALTH':
            base_cost *= Decimal('2.0')
        elif self.shipping_type == 'DEAD_DROP':
            base_cost *= Decimal('1.2')
        
        return base_cost


class DeadDropLocation(PrivacyModel):
    """Dead drop locations for local deals"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Setup'),
        ('ACTIVE', 'Active'),
        ('USED', 'Used'),
        ('COMPROMISED', 'Compromised'),
        ('EXPIRED', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='dead_drop')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='dead_drops')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dead_drops')
    
    # Location (encrypted)
    encrypted_coordinates = models.TextField()  # GPS coordinates encrypted
    encrypted_description = models.TextField()  # Detailed description encrypted
    general_area = models.CharField(max_length=100)  # City/Region (non-specific)
    
    # Timing
    drop_time = models.DateTimeField()
    pickup_deadline = models.DateTimeField()
    
    # Security
    drop_code = models.CharField(max_length=20)  # Code word for verification
    photo_proof = models.TextField(blank=True)  # Encrypted photo of location
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Confirmation
    dropped_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'pickup_deadline']),
            models.Index(fields=['vendor', 'status']),
        ]
    
    def set_coordinates(self, latitude, longitude, description):
        """Encrypt and store coordinates"""
        import json
        coords_data = {
            'lat': str(latitude),
            'lng': str(longitude),
            'accuracy': 'approximate'  # Never store exact coordinates
        }
        self.encrypted_coordinates = SECRET_MANAGER.encrypt_sensitive_data(json.dumps(coords_data))
        self.encrypted_description = SECRET_MANAGER.encrypt_sensitive_data(description)
    
    def get_coordinates(self):
        """Decrypt coordinates for authorized user"""
        import json
        if not self.encrypted_coordinates:
            return None
        
        decrypted = SECRET_MANAGER.decrypt_sensitive_data(self.encrypted_coordinates)
        return json.loads(decrypted)
    
    def generate_drop_code(self):
        """Generate unique drop code"""
        import secrets
        self.drop_code = secrets.token_urlsafe(10)[:10]
    
    def mark_as_dropped(self):
        """Mark package as dropped"""
        self.status = 'ACTIVE'
        self.dropped_at = timezone.now()
        self.save()
    
    def mark_as_picked_up(self):
        """Mark package as picked up"""
        self.status = 'USED'
        self.picked_up_at = timezone.now()
        self.save()
    
    def check_expiry(self):
        """Check if dead drop has expired"""
        if timezone.now() > self.pickup_deadline:
            self.status = 'EXPIRED'
            self.save()
            return True
        return False


class ShippingAddress(PrivacyModel):
    """Encrypted shipping addresses with auto-delete"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='shipping_address')
    
    # Encrypted address fields
    encrypted_name = models.TextField()
    encrypted_address_line1 = models.TextField()
    encrypted_address_line2 = models.TextField(blank=True)
    encrypted_city = models.TextField()
    encrypted_state = models.TextField()
    encrypted_postal_code = models.TextField()
    encrypted_country = models.TextField()
    
    # Additional instructions (encrypted)
    encrypted_instructions = models.TextField(blank=True)
    
    # Auto-delete settings
    auto_delete_enabled = models.BooleanField(default=True)
    auto_delete_after_days = models.IntegerField(default=7)
    delete_scheduled_for = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    tracking_number = models.CharField(max_length=255, blank=True)
    encrypted_tracking = models.TextField(blank=True)  # Encrypted tracking details
    
    # Decoy package info
    uses_decoy = models.BooleanField(default=False)
    decoy_description = models.TextField(blank=True)
    
    # Security
    address_hash = models.CharField(max_length=64, unique=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['delete_scheduled_for']),
        ]
    
    def set_address(self, address_data):
        """Encrypt and store address"""
        fields_to_encrypt = [
            'name', 'address_line1', 'address_line2', 
            'city', 'state', 'postal_code', 'country'
        ]
        
        for field in fields_to_encrypt:
            if field in address_data:
                encrypted_field = f'encrypted_{field}'
                value = address_data.get(field, '')
                setattr(self, encrypted_field, SECRET_MANAGER.encrypt_sensitive_data(value))
        
        # Generate address hash for duplicate detection
        hash_data = f"{address_data.get('address_line1', '')}{address_data.get('postal_code', '')}"
        self.address_hash = hashlib.sha256(hash_data.encode()).hexdigest()
        
        # Schedule auto-delete
        if self.auto_delete_enabled:
            self.delete_scheduled_for = timezone.now() + timedelta(days=self.auto_delete_after_days)
    
    def get_address(self):
        """Decrypt address for authorized viewing"""
        address = {}
        fields_to_decrypt = [
            'name', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country'
        ]
        
        for field in fields_to_decrypt:
            encrypted_field = f'encrypted_{field}'
            encrypted_value = getattr(self, encrypted_field)
            if encrypted_value:
                address[field] = SECRET_MANAGER.decrypt_sensitive_data(encrypted_value)
        
        return address
    
    def set_tracking(self, tracking_number, encrypted=True):
        """Set tracking number with optional encryption"""
        if encrypted:
            self.encrypted_tracking = SECRET_MANAGER.encrypt_sensitive_data(tracking_number)
            self.tracking_number = tracking_number[:4] + '****' + tracking_number[-4:]  # Partial for display
        else:
            self.tracking_number = tracking_number
    
    def auto_delete(self):
        """Auto-delete shipping information after delivery"""
        if not self.auto_delete_enabled:
            return False
        
        if timezone.now() >= self.delete_scheduled_for:
            # Overwrite with random data before deletion
            import secrets
            fields_to_clear = [
                'encrypted_name', 'encrypted_address_line1', 'encrypted_address_line2',
                'encrypted_city', 'encrypted_state', 'encrypted_postal_code', 
                'encrypted_country', 'encrypted_instructions'
            ]
            
            for field in fields_to_clear:
                setattr(self, field, secrets.token_urlsafe(32))
            
            self.save()
            self.delete()
            return True
        
        return False


class ShippingOrigin(PrivacyModel):
    """Vendor shipping origins for filtering"""
    
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE, related_name='shipping_origins')
    country = models.CharField(max_length=2)  # ISO country code
    region = models.CharField(max_length=100, blank=True)  # State/Province
    
    # Capabilities
    express_available = models.BooleanField(default=False)
    stealth_available = models.BooleanField(default=True)
    dead_drop_available = models.BooleanField(default=False)
    
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['vendor', 'country', 'region']
        indexes = [
            models.Index(fields=['country', 'region']),
        ]