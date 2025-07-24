from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
import uuid

User = get_user_model()


class Vendor(PrivacyModel):
    TRUST_LEVELS = [
        ('NEW', 'New Vendor'),
        ('TRUSTED', 'Trusted'),
        ('VERIFIED', 'Verified'),
        ('PREMIUM', 'Premium'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor')
    vendor_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    trust_level = models.CharField(max_length=20, choices=TRUST_LEVELS, default='NEW')
    total_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    low_stock_threshold = models.IntegerField(default=5)
    response_time = models.DurationField(null=True, blank=True)
    
    vacation_mode = models.BooleanField(default=False)
    vacation_message = models.TextField(blank=True)
    vacation_started = models.DateTimeField(null=True, blank=True)
    vacation_ends = models.DateTimeField(null=True, blank=True)
    
    pgp_key = models.TextField(blank=True, null=True)
    bond_paid = models.BooleanField(default=False)
    bond_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0.0)
    bond_currency = models.CharField(max_length=3, choices=[('BTC', 'Bitcoin'), ('XMR', 'Monero')], default='BTC')
    bond_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.vendor_name
    
    @property
    def is_on_vacation(self):
        if not self.vacation_mode:
            return False
        
        if self.vacation_ends and timezone.now() > self.vacation_ends:
            self.deactivate_vacation_mode()
            return False
        
        return True
    
    def activate_vacation_mode(self, message='', ends_at=None):
        self.vacation_mode = True
        self.vacation_message = message
        self.vacation_started = timezone.now()
        self.vacation_ends = ends_at
        self.save()
    
    def deactivate_vacation_mode(self):
        self.vacation_mode = False
        self.vacation_message = ''
        self.vacation_started = None
        self.vacation_ends = None
        self.save()
    
    class Meta:
        indexes = [
            models.Index(fields=['is_approved', 'is_active']),
            models.Index(fields=['trust_level']),
            models.Index(fields=['rating']),
            models.Index(fields=['vacation_mode']),
        ]


class VendorRating(PrivacyModel):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['vendor', 'user']
    
    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.rating}/5"


class Promotion(PrivacyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='promotions')
    title = models.CharField(max_length=200)
    description = models.TextField()
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    code = models.CharField(max_length=50, unique=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    max_uses = models.IntegerField(default=100)
    current_uses = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.title}"
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['vendor', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]


class Feedback(PrivacyModel):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='feedback')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_feedback')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    vendor_response = models.TextField(blank=True)
    response_date = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Feedback for {self.vendor.vendor_name} - {self.rating} stars"
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor', 'is_public']),
            models.Index(fields=['rating']),
            models.Index(fields=['-created_at']),
        ]


class VendorNotification(PrivacyModel):
    NOTIFICATION_TYPES = [
        ('low_stock', 'Low Stock Alert'),
        ('new_order', 'New Order'),
        ('new_feedback', 'New Feedback'),
        ('promotion_expiry', 'Promotion Expiring'),
        ('system', 'System Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.title}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vendor', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['-created_at']),
        ]


class SubVendor(PrivacyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    main_vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='sub_vendors')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='sub_vendor')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_subvendors')
    
    can_view_orders = models.BooleanField(default=True)
    can_respond_messages = models.BooleanField(default=True)
    can_update_tracking = models.BooleanField(default=False)
    can_process_refunds = models.BooleanField(default=False)
    
    daily_message_limit = models.IntegerField(default=100)
    messages_sent_today = models.IntegerField(default=0)
    last_message_reset = models.DateField(default=timezone.now)
    
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    def reset_daily_message_count(self):
        today = timezone.now().date()
        if self.last_message_reset < today:
            self.messages_sent_today = 0
            self.last_message_reset = today
            self.save()
    
    def can_send_message(self):
        self.reset_daily_message_count()
        return self.messages_sent_today < self.daily_message_limit
    
    def increment_message_count(self):
        self.reset_daily_message_count()
        self.messages_sent_today += 1
        self.save()
    
    def __str__(self):
        return f"{self.main_vendor.vendor_name} - {self.user.username}"
    
    class Meta:
        indexes = [
            models.Index(fields=['main_vendor', 'is_active']),
            models.Index(fields=['user']),
        ]


class SubVendorActivityLog(PrivacyModel):
    ACTION_CHOICES = [
        ('account_created', 'Account Created'),
        ('account_deactivated', 'Account Deactivated'),
        ('permissions_updated', 'Permissions Updated'),
        ('order_viewed', 'Order Viewed'),
        ('message_sent', 'Message Sent'),
        ('tracking_updated', 'Tracking Updated'),
        ('refund_processed', 'Refund Processed'),
        ('login', 'Login'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_vendor = models.ForeignKey(SubVendor, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.sub_vendor} - {self.get_action_display()}"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sub_vendor', '-created_at']),
            models.Index(fields=['action']),
        ]
