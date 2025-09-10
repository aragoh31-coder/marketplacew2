from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from core.base_models import PrivacyModel
import uuid
import secrets
from datetime import timedelta


class User(AbstractUser, PrivacyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    pgp_public_key = models.TextField(blank=True, null=True)
    pgp_fingerprint = models.CharField(max_length=40, blank=True, db_index=True)
    pgp_login_enabled = models.BooleanField(default=False)
    pgp_challenge = models.TextField(blank=True, null=True)
    pgp_challenge_expires = models.DateTimeField(null=True, blank=True)
    
    panic_password = models.CharField(max_length=255, blank=True, null=True)
    session_fingerprints = models.JSONField(default=dict)
    failed_login_attempts = models.IntegerField(default=0)
    
    default_currency = models.CharField(
        max_length=10, 
        choices=[
            ('BTC', 'Bitcoin'),
            ('XMR', 'Monero'),
            ('USD', 'USD'),
            ('EUR', 'Euro'),
        ],
        default='BTC'
    )
    default_shipping_country = models.CharField(max_length=100, blank=True, default='')
    
    feedback_score = models.FloatField(default=0.0)
    total_trades = models.IntegerField(default=0)
    positive_feedback_count = models.IntegerField(default=0)
    
    is_vendor = models.BooleanField(default=False)
    account_created = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    
    def get_trust_level(self):
        """Calculate trust level based on trades and feedback"""
        if self.total_trades == 0:
            return "New User"
        
        positive_rate = (self.positive_feedback_count / self.total_trades) * 100
        
        if self.total_trades >= 100 and positive_rate >= 95:
            return "Legendary"
        elif self.total_trades >= 50 and positive_rate >= 90:
            return "Trusted"
        elif self.total_trades >= 20 and positive_rate >= 85:
            return "Established"
        elif self.total_trades >= 5 and positive_rate >= 80:
            return "Regular"
        else:
            return "Beginner"
    
    def generate_pgp_challenge(self):
        """Generate a new PGP challenge for 2FA authentication"""
        challenge = secrets.token_urlsafe(32)
        self.pgp_challenge = challenge
        self.pgp_challenge_expires = timezone.now() + timedelta(minutes=5)
        self.save()
        return challenge
    
    def verify_pgp_challenge(self, challenge_code):
        """Verify a PGP challenge response"""
        if not self.pgp_challenge or not self.pgp_challenge_expires:
            return False
        
        if timezone.now() > self.pgp_challenge_expires:
            return False
        
        if self.pgp_challenge == challenge_code:
            self.pgp_challenge = None
            self.pgp_challenge_expires = None
            self.save()
            return True
        
        return False
    
    def __str__(self):
        return self.username


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64)  # Store hashed IP for privacy
    user_agent = models.CharField(max_length=200)
    success = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']


