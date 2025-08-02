from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import hashlib
import json


class SecurityEvent(models.Model):
    """Track security events and suspicious activities"""
    EVENT_TYPES = [
        ('login_attempt', 'Login Attempt'),
        ('failed_login', 'Failed Login'),
        ('bot_detected', 'Bot Detected'),
        ('rate_limited', 'Rate Limited'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('captcha_failed', 'CAPTCHA Failed'),
        ('ip_change', 'IP Address Change'),
        ('session_hijack', 'Session Hijack Attempt'),
        ('withdrawal_attempt', 'Withdrawal Attempt'),
        ('admin_action', 'Admin Action'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    
    details = models.JSONField(default=dict, blank=True)
    risk_score = models.IntegerField(default=0)
    
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='resolved_security_events'
    )
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'event_type', 'created_at']),
            models.Index(fields=['risk_score', 'resolved']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']


class BotDetectionLog(models.Model):
    """Log bot detection attempts and patterns"""
    DETECTION_METHODS = [
        ('user_agent', 'User Agent Analysis'),
        ('behavior', 'Behavioral Analysis'),
        ('timing', 'Timing Analysis'),
        ('honeypot', 'Honeypot Triggered'),
        ('captcha', 'CAPTCHA Failed'),
        ('rate_limit', 'Rate Limit Exceeded'),
        ('pattern', 'Pattern Recognition'),
    ]
    
    session_key = models.CharField(max_length=40, db_index=True)
    detection_method = models.CharField(max_length=20, choices=DETECTION_METHODS)
    
    user_agent = models.TextField()
    confidence_score = models.IntegerField(default=0)  # 0-100
    details = models.JSONField(default=dict)
    
    blocked = models.BooleanField(default=False)
    challenge_issued = models.BooleanField(default=False)
    
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'detected_at']),
            models.Index(fields=['detection_method', 'confidence_score']),
        ]
        ordering = ['-detected_at']


class RateLimitLog(models.Model):
    """Track rate limiting events"""
    LIMIT_TYPES = [
        ('login', 'Login Attempts'),
        ('registration', 'Registration Attempts'),
        ('withdrawal', 'Withdrawal Requests'),
        ('form_submission', 'Form Submissions'),
        ('api_request', 'API Requests'),
        ('captcha', 'CAPTCHA Attempts'),
    ]
    
    session_key = models.CharField(max_length=40, db_index=True)
    limit_type = models.CharField(max_length=20, choices=LIMIT_TYPES)
    
    attempts_count = models.IntegerField()
    limit_threshold = models.IntegerField()
    time_window = models.IntegerField()  # seconds
    
    blocked = models.BooleanField(default=True)
    cooldown_until = models.DateTimeField()
    
    triggered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'limit_type']),
            models.Index(fields=['triggered_at']),
        ]
        ordering = ['-triggered_at']


class CaptchaAttempt(models.Model):
    """Track CAPTCHA attempts and success rates"""
    session_key = models.CharField(max_length=40, db_index=True)
    challenge_type = models.CharField(max_length=20, default='math')
    
    challenge_data = models.JSONField(default=dict)
    user_answer = models.CharField(max_length=100, blank=True)
    correct_answer = models.CharField(max_length=100)
    
    success = models.BooleanField(default=False)
    attempts_count = models.IntegerField(default=1)
    time_taken = models.FloatField(null=True, blank=True)  # seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'success']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']


class SecurityAuditLog(models.Model):
    """Comprehensive audit log for all security-related actions"""
    ACTION_CATEGORIES = [
        ('authentication', 'Authentication'),
        ('authorization', 'Authorization'),
        ('data_access', 'Data Access'),
        ('configuration', 'Configuration Change'),
        ('security_event', 'Security Event'),
        ('admin_action', 'Admin Action'),
        ('system_event', 'System Event'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=20, choices=ACTION_CATEGORIES)
    action = models.CharField(max_length=100)
    
    target_model = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict)
    
    session_key = models.CharField(max_length=40, blank=True)
    user_agent = models.TextField(blank=True)
    
    risk_level = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='low'
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'category', 'timestamp']),
            models.Index(fields=['risk_level', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']


class SessionSecurity(models.Model):
    """Track session security metrics"""
    session_key = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    
    risk_score = models.IntegerField(default=0)
    bot_probability = models.FloatField(default=0.0)
    
    first_seen = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    page_views = models.IntegerField(default=0)
    
    avg_page_time = models.FloatField(default=0.0)
    form_submissions = models.IntegerField(default=0)
    failed_attempts = models.IntegerField(default=0)
    
    is_suspicious = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    requires_verification = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['user', 'last_activity']),
            models.Index(fields=['risk_score', 'is_suspicious']),
        ]
