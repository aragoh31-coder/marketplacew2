from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class VendorBond(models.Model):
    """Vendor bonding system for security deposits"""
    BOND_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('released', 'Released'),
        ('forfeited', 'Forfeited'),
        ('expired', 'Expired'),
    ]
    
    vendor = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_bond')
    bond_amount = models.DecimalField(
        max_digits=16, 
        decimal_places=8, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, choices=[('btc', 'Bitcoin'), ('xmr', 'Monero')])
    status = models.CharField(max_length=20, choices=BOND_STATUS_CHOICES, default='pending')
    
    required_amount = models.DecimalField(max_digits=16, decimal_places=8)
    paid_amount = models.DecimalField(max_digits=16, decimal_places=8, default=Decimal('0'))
    bond_address = models.CharField(max_length=255, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    deposit_tx_hash = models.CharField(max_length=255, blank=True, null=True)
    release_tx_hash = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]


class BroadcastMessage(models.Model):
    """System-wide broadcast messages"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('maintenance', 'Maintenance'),
        ('security', 'Security Alert'),
        ('update', 'System Update'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='info')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    target_all_users = models.BooleanField(default=True)
    target_vendors = models.BooleanField(default=False)
    target_buyers = models.BooleanField(default=False)
    target_admins = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    show_on_homepage = models.BooleanField(default=True)
    show_in_dashboard = models.BooleanField(default=True)
    dismissible = models.BooleanField(default=True)
    
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_broadcasts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_time', 'end_time']),
            models.Index(fields=['priority', 'message_type']),
        ]


class MessageAlert(models.Model):
    """User message alerts and notifications"""
    ALERT_TYPE_CHOICES = [
        ('new_message', 'New Message'),
        ('order_update', 'Order Update'),
        ('dispute_update', 'Dispute Update'),
        ('system_alert', 'System Alert'),
        ('security_alert', 'Security Alert'),
        ('payment_alert', 'Payment Alert'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    
    related_object_type = models.CharField(max_length=50, null=True, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['alert_type', 'created_at']),
        ]


class SystemBackup(models.Model):
    """System backup tracking and management"""
    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Backup'),
        ('incremental', 'Incremental'),
        ('database', 'Database Only'),
        ('files', 'Files Only'),
        ('config', 'Configuration'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('corrupted', 'Corrupted'),
    ]
    
    backup_id = models.UUIDField(default=uuid.uuid4, unique=True)
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    
    description = models.TextField(blank=True)
    includes_database = models.BooleanField(default=True)
    includes_media = models.BooleanField(default=True)
    includes_logs = models.BooleanField(default=False)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'backup_type']),
            models.Index(fields=['created_at']),
        ]


class TorServiceStatus(models.Model):
    """Tor onion service monitoring and status"""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('degraded', 'Degraded'),
        ('maintenance', 'Maintenance'),
    ]
    
    onion_address = models.CharField(max_length=56, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    
    response_time_ms = models.IntegerField(null=True, blank=True)
    uptime_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    circuit_count = models.IntegerField(default=0)
    descriptor_published = models.BooleanField(default=False)
    
    last_check = models.DateTimeField(auto_now=True)
    last_online = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    consecutive_failures = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-last_check']
        indexes = [
            models.Index(fields=['status', 'last_check']),
            models.Index(fields=['onion_address']),
        ]


class AdminSecurityLog(models.Model):
    """Enhanced admin security logging"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('password_change', 'Password Change'),
        ('2fa_enable', '2FA Enabled'),
        ('2fa_disable', '2FA Disabled'),
        ('user_action', 'User Action'),
        ('system_change', 'System Change'),
        ('security_alert', 'Security Alert'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_security_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='low')
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    session_key = models.CharField(max_length=40, blank=True)
    
    target_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='targeted_by_admin'
    )
    action_details = models.JSONField(default=dict)
    
    suspicious = models.BooleanField(default=False)
    requires_review = models.BooleanField(default=False)
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_security_logs'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_user', 'action', 'created_at']),
            models.Index(fields=['severity', 'suspicious']),
            models.Index(fields=['requires_review', 'reviewed']),
        ]
