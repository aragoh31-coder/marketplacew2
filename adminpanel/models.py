from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
import uuid
import hashlib

User = get_user_model()


class AdminLog(PrivacyModel):
    ACTION_TYPES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.action_type} {self.target_model}"


class SystemSettings(PrivacyModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.key}: {self.value[:50]}"


class AdminProfile(models.Model):
    """Extended admin profile with enhanced security"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    
    secondary_password_hash = models.CharField(max_length=128, blank=True, null=True)
    
    pgp_public_key = models.TextField(blank=True, null=True)
    pgp_fingerprint = models.CharField(max_length=40, blank=True, null=True)
    pgp_required = models.BooleanField(default=True)
    
    require_triple_auth = models.BooleanField(default=True)
    session_timeout = models.IntegerField(default=3600)  # 1 hour
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def set_secondary_password(self, password):
        """Set secondary password with hashing"""
        self.secondary_password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_secondary_password(self, password):
        """Check secondary password"""
        if not self.secondary_password_hash:
            return False
        return self.secondary_password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def __str__(self):
        return f"Admin Profile: {self.user.username}"


class AdminAction(models.Model):
    """Log of admin actions for audit trail"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('user_view', 'User View'),
        ('user_edit', 'User Edit'),
        ('withdrawal_approve', 'Withdrawal Approve'),
        ('withdrawal_reject', 'Withdrawal Reject'),
        ('security_alert', 'Security Alert'),
        ('system_config', 'System Configuration'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_actions')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    session_id = models.CharField(max_length=64, blank=True)
    user_agent_hash = models.CharField(max_length=32, blank=True)
    
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['admin_user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['target_user', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.action} at {self.timestamp}"


class SecurityAlert(models.Model):
    """Security alerts for admin attention"""
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ALERT_TYPES = [
        ('failed_login', 'Failed Login Attempts'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('balance_discrepancy', 'Balance Discrepancy'),
        ('bot_detection', 'Bot Detection'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('security_breach', 'Security Breach'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['severity', 'is_resolved', 'created_at']),
            models.Index(fields=['alert_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def resolve(self, admin_user, notes=""):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_by = admin_user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()
    
    def __str__(self):
        return f"{self.get_severity_display()} - {self.title}"
