from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from core.base_models import PrivacyModel
import uuid
import secrets
from datetime import timedelta
import pyotp
import qrcode
import io
import base64


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
    
    totp_secret = models.CharField(max_length=32, blank=True)
    totp_enabled = models.BooleanField(default=False)
    totp_backup_codes = models.JSONField(default=list, blank=True)
    totp_last_used_counter = models.IntegerField(default=0)
    
    
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
    
    def requires_2fa(self):
        """Check if user has any 2FA method enabled"""
        return getattr(self, 'totp_enabled', False) or getattr(self, 'pgp_2fa_enabled', False)
    
    def generate_totp_secret(self):
        """Generate new TOTP secret"""
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            self.save(update_fields=['totp_secret'])
        return self.totp_secret
    
    def get_totp_uri(self):
        """Get TOTP URI for QR code generation"""
        if not self.totp_secret:
            self.generate_totp_secret()
        
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.username,
            issuer_name="Secure Marketplace"
        )
    
    def generate_qr_code(self):
        """Generate QR code for TOTP setup"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.get_totp_uri())
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_totp(self, token):
        """Verify TOTP token"""
        if not self.totp_secret or not self.totp_enabled:
            return False
        
        totp = pyotp.TOTP(self.totp_secret)
        
        import time
        current_time = int(time.time())
        
        for time_offset in [0, -30, 30]:
            if totp.verify(token, for_time=current_time + time_offset):
                return True
        
        return False
    
    def verify_backup_code(self, code):
        """Verify and consume backup code"""
        if code in self.totp_backup_codes:
            self.totp_backup_codes.remove(code)
            self.save(update_fields=['totp_backup_codes'])
            return True
        return False
    
    def generate_backup_codes(self, count=10):
        """Generate new backup codes"""
        import secrets
        import string
        
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            codes.append(code)
        
        self.totp_backup_codes = codes
        self.save(update_fields=['totp_backup_codes'])
        return codes
    
    def has_any_2fa(self):
        """Check if user has any 2FA method enabled"""
        return self.totp_enabled
    
    def disable_totp(self):
        """Disable TOTP 2FA"""
        self.totp_enabled = False
        self.totp_secret = ''
        self.totp_backup_codes = []
        self.save(update_fields=['totp_enabled', 'totp_secret', 'totp_backup_codes'])


class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64)  # Store hashed IP for privacy
    user_agent = models.CharField(max_length=200)
    success = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']


class UserSession(PrivacyModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, unique=True)
    fingerprint = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    last_activity = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:8]}"
