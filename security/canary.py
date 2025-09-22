from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.base_models import PrivacyModel
from config.security_config import SECRET_MANAGER
import hashlib
import gnupg
from datetime import timedelta
import uuid

User = get_user_model()


class CanaryPage(PrivacyModel):
    """Warrant canary with PGP-signed updates"""
    
    CANARY_STATUS = [
        ('ACTIVE', 'Active - No Warrants'),
        ('EXPIRED', 'Expired - Check Status'),
        ('COMPROMISED', 'Compromised - Leave Immediately'),
        ('UPDATED', 'Recently Updated'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Canary message
    message = models.TextField()
    status = models.CharField(max_length=20, choices=CANARY_STATUS, default='ACTIVE')
    
    # PGP signing
    pgp_signed_message = models.TextField()
    signing_key_fingerprint = models.CharField(max_length=40)
    
    # Timing
    valid_until = models.DateTimeField()
    last_updated = models.DateTimeField(auto_now=True)
    update_frequency_days = models.IntegerField(default=7)  # Weekly updates
    
    # Verification
    previous_hash = models.CharField(max_length=64, blank=True)
    current_hash = models.CharField(max_length=64)
    
    # Admin settings
    auto_expire = models.BooleanField(default=True)
    alert_before_days = models.IntegerField(default=2)  # Alert 2 days before expiry
    
    # Statistics
    times_verified = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        get_latest_by = 'created_at'
    
    @classmethod
    def create_canary(cls, admin_user):
        """Create new canary statement"""
        canary = cls()
        
        # Standard canary message
        canary.message = f"""
-----BEGIN CANARY STATEMENT-----
Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

This is the warrant canary for our marketplace.

As of this date, we have NOT received any:
- National Security Letters
- FISA court orders  
- Gag orders
- Warrants from any government entity
- Requests for user data that we were prohibited from disclosing

We have NOT installed any backdoors, monitoring or logging at the request of any third party.

We have NOT been compromised or suffered any security breach affecting user data.

This canary will be updated every {canary.update_frequency_days} days.
If this canary is not updated by the expiration date, you should assume the worst.

Next update expected by: {(timezone.now() + timedelta(days=canary.update_frequency_days)).strftime('%Y-%m-%d')}

Verify this message with our PGP key.
-----END CANARY STATEMENT-----
        """
        
        # Set expiration
        canary.valid_until = timezone.now() + timedelta(days=canary.update_frequency_days)
        
        # Generate hash chain
        last_canary = cls.objects.filter(status='ACTIVE').order_by('-created_at').first()
        if last_canary:
            canary.previous_hash = last_canary.current_hash
        
        # Sign the message
        canary.sign_message(admin_user)
        
        # Generate current hash
        canary.generate_hash()
        
        canary.save()
        return canary
    
    def sign_message(self, admin_user):
        """Sign canary message with PGP"""
        gpg = gnupg.GPG()
        
        # Get admin's PGP key
        if not admin_user.pgp_fingerprint:
            raise ValueError("Admin must have PGP key for signing")
        
        self.signing_key_fingerprint = admin_user.pgp_fingerprint
        
        # Sign the message
        signed = gpg.sign(
            self.message,
            keyid=admin_user.pgp_fingerprint,
            passphrase=None  # Would prompt for passphrase in production
        )
        
        self.pgp_signed_message = str(signed)
    
    def verify_signature(self):
        """Verify PGP signature of canary"""
        gpg = gnupg.GPG()
        
        verified = gpg.verify(self.pgp_signed_message)
        
        if verified.valid:
            self.times_verified += 1
            self.save()
            return True, verified.fingerprint
        
        return False, None
    
    def generate_hash(self):
        """Generate hash for blockchain-like verification"""
        hash_data = f"{self.message}{self.previous_hash}{self.created_at}"
        self.current_hash = hashlib.sha256(hash_data.encode()).hexdigest()
    
    def check_expiry(self):
        """Check if canary has expired"""
        if timezone.now() > self.valid_until:
            self.status = 'EXPIRED'
            self.save()
            return True
        
        # Check if alert needed
        alert_date = self.valid_until - timedelta(days=self.alert_before_days)
        if timezone.now() > alert_date:
            return 'ALERT'
        
        return False
    
    @classmethod
    def get_current_canary(cls):
        """Get the current active canary"""
        return cls.objects.filter(status='ACTIVE').order_by('-created_at').first()


class MirrorSite(PrivacyModel):
    """Mirror/backup .onion addresses"""
    
    MIRROR_STATUS = [
        ('ACTIVE', 'Active'),
        ('STANDBY', 'Standby'),
        ('COMPROMISED', 'Compromised'),
        ('RETIRED', 'Retired'),
    ]
    
    onion_address = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=MIRROR_STATUS, default='STANDBY')
    
    # Health checking
    last_health_check = models.DateTimeField(null=True, blank=True)
    is_healthy = models.BooleanField(default=True)
    response_time_ms = models.IntegerField(default=0)
    
    # Load balancing
    traffic_weight = models.IntegerField(default=1)  # Weight for load distribution
    current_connections = models.IntegerField(default=0)
    
    # Security
    ssl_fingerprint = models.CharField(max_length=64, blank=True)
    
    class Meta:
        ordering = ['is_primary', '-traffic_weight']
    
    @classmethod
    def get_active_mirrors(cls):
        """Get all active mirror addresses"""
        return cls.objects.filter(
            status='ACTIVE',
            is_healthy=True
        ).order_by('-traffic_weight')
    
    def health_check(self):
        """Perform health check on mirror"""
        import requests
        import time
        
        try:
            start = time.time()
            
            # Check through Tor
            session = requests.Session()
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            
            response = session.get(
                f'http://{self.onion_address}/health',
                timeout=30
            )
            
            self.response_time_ms = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                self.is_healthy = True
                self.last_health_check = timezone.now()
            else:
                self.is_healthy = False
            
        except Exception as e:
            self.is_healthy = False
            
        self.save()
        return self.is_healthy


class AntiPhishingPhrase(PrivacyModel):
    """Unique anti-phishing phrases per user"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='anti_phishing')
    phrase = models.CharField(max_length=50)
    
    # Display settings
    show_on_login = models.BooleanField(default=True)
    show_on_deposit = models.BooleanField(default=True)
    show_on_withdraw = models.BooleanField(default=True)
    
    # Verification
    phrase_hash = models.CharField(max_length=64)
    last_verified = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def generate_phrase(self):
        """Generate unique phrase for user"""
        import random
        
        # Word lists for phrase generation
        adjectives = [
            'swift', 'bright', 'cosmic', 'crystal', 'golden',
            'silver', 'mystic', 'quantum', 'stellar', 'lunar'
        ]
        
        nouns = [
            'phoenix', 'dragon', 'falcon', 'wolf', 'eagle',
            'mountain', 'ocean', 'thunder', 'lightning', 'shadow'
        ]
        
        numbers = random.randint(100, 999)
        
        self.phrase = f"{random.choice(adjectives)}-{random.choice(nouns)}-{numbers}"
        self.phrase_hash = hashlib.sha256(self.phrase.encode()).hexdigest()
        
        return self.phrase
    
    def verify_phrase(self, submitted_phrase):
        """Verify submitted phrase matches"""
        submitted_hash = hashlib.sha256(submitted_phrase.encode()).hexdigest()
        
        if submitted_hash == self.phrase_hash:
            self.last_verified = timezone.now()
            self.save()
            return True
        
        return False


class TwoFactorAuth(PrivacyModel):
    """2FA with PGP and TOTP options"""
    
    TWO_FA_METHODS = [
        ('PGP', 'PGP Challenge'),
        ('TOTP', 'Time-based OTP'),
        ('BOTH', 'PGP and TOTP'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='two_factor')
    
    method = models.CharField(max_length=10, choices=TWO_FA_METHODS, default='PGP')
    is_enabled = models.BooleanField(default=False)
    
    # PGP challenge settings
    pgp_challenge_length = models.IntegerField(default=32)
    
    # TOTP settings
    totp_secret = models.CharField(max_length=32, blank=True)
    backup_codes = models.JSONField(default=list)
    
    # Mandatory for vendors
    mandatory_for_vendor = models.BooleanField(default=True)
    
    # Recovery
    recovery_email_encrypted = models.TextField(blank=True)
    
    # Statistics
    successful_verifications = models.IntegerField(default=0)
    failed_attempts = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_enabled']),
        ]
    
    def generate_totp_secret(self):
        """Generate TOTP secret"""
        import pyotp
        
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes"""
        import secrets
        
        self.backup_codes = []
        for _ in range(count):
            code = f"{secrets.token_hex(4)}-{secrets.token_hex(4)}"
            self.backup_codes.append(hashlib.sha256(code.encode()).hexdigest())
        
        return self.backup_codes
    
    def verify_totp(self, token):
        """Verify TOTP token"""
        if not self.totp_secret:
            return False
        
        import pyotp
        
        totp = pyotp.TOTP(self.totp_secret)
        
        if totp.verify(token, valid_window=1):
            self.successful_verifications += 1
            self.last_used = timezone.now()
            self.save()
            return True
        
        self.failed_attempts += 1
        self.save()
        return False
    
    def verify_pgp_challenge(self, response):
        """Verify PGP challenge response"""
        import gnupg
        from django.conf import settings
        import hashlib
        
        if not self.pgp_public_key:
            return False
        
        try:
            gpg = gnupg.GPG(gnupghome=settings.GPG_HOME_DIR)
            
            # Import user's public key
            import_result = gpg.import_keys(self.pgp_public_key)
            if not import_result.count:
                return False
            
            # Verify the response is properly signed
            verified = gpg.verify(response)
            if not verified:
                return False
            
            # Extract and verify challenge code
            decrypted = gpg.decrypt(response)
            if not decrypted.ok:
                return False
            
            # Check if decrypted message matches our challenge
            expected_hash = hashlib.sha256(
                f"{self.user.username}:{self.last_login}".encode()
            ).hexdigest()[:16]
            
            return expected_hash in str(decrypted)
            
        except Exception as e:
            logger.error(f"PGP verification error: {e}")
            return False


class ReferralSystem(PrivacyModel):
    """Referral links with commission system"""
    
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referral_links')
    
    # Unique referral code
    referral_code = models.CharField(max_length=20, unique=True)
    
    # Commission settings (admin configurable)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    commission_duration_days = models.IntegerField(default=90)  # How long commissions last
    
    # Tracking
    clicks = models.IntegerField(default=0)
    signups = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    
    # Earnings
    total_commission_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_commission_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['referral_code']),
            models.Index(fields=['referrer', 'is_active']),
        ]
    
    def generate_code(self):
        """Generate unique referral code"""
        import secrets
        
        while True:
            code = secrets.token_urlsafe(10)[:10]
            if not ReferralSystem.objects.filter(referral_code=code).exists():
                self.referral_code = code
                break
        
        return self.referral_code
    
    def calculate_commission(self, order_amount, currency='BTC'):
        """Calculate commission for referred order"""
        commission = order_amount * (self.commission_percentage / 100)
        
        if currency == 'BTC':
            self.total_commission_btc += commission
        else:
            self.total_commission_xmr += commission
        
        self.save()
        return commission


class TextCaptcha(PrivacyModel):
    """Text-based CAPTCHA for Tor users"""
    
    CAPTCHA_TYPES = [
        ('MATH', 'Math Problem'),
        ('WORD', 'Word Problem'),
        ('CHESS', 'Chess Notation'),
    ]
    
    captcha_type = models.CharField(max_length=10, choices=CAPTCHA_TYPES)
    question = models.TextField()
    answer = models.CharField(max_length=50)
    answer_hash = models.CharField(max_length=64)
    
    # Usage tracking
    times_shown = models.IntegerField(default=0)
    times_solved = models.IntegerField(default=0)
    
    # Expiry
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['expires_at']),
        ]
    
    @classmethod
    def generate_math_captcha(cls):
        """Generate math CAPTCHA"""
        import random
        
        a = random.randint(10, 99)
        b = random.randint(10, 99)
        operation = random.choice(['+', '-', '*'])
        
        if operation == '+':
            answer = a + b
            question = f"What is {a} + {b}?"
        elif operation == '-':
            answer = a - b
            question = f"What is {a} - {b}?"
        else:  # multiplication
            a = random.randint(2, 20)  # Smaller numbers for multiplication
            b = random.randint(2, 20)
            answer = a * b
            question = f"What is {a} × {b}?"
        
        captcha = cls(
            captcha_type='MATH',
            question=question,
            answer=str(answer),
            answer_hash=hashlib.sha256(str(answer).encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        return captcha
    
    def verify_answer(self, submitted_answer):
        """Verify CAPTCHA answer"""
        if timezone.now() > self.expires_at:
            return False
        
        submitted_hash = hashlib.sha256(submitted_answer.encode()).hexdigest()
        
        if submitted_hash == self.answer_hash:
            self.times_solved += 1
            self.save()
            return True
        
        return False