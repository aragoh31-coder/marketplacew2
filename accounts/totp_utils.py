import pyotp
import secrets
import string
from django.utils import timezone
from datetime import timedelta

class TOTPManager:
    """Utility class for managing TOTP operations"""
    
    @staticmethod
    def generate_secret():
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup recovery codes"""
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        return codes
    
    @staticmethod
    def get_current_code(secret):
        """Get current TOTP code for testing purposes"""
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    @staticmethod
    def verify_code(secret, code, window=1):
        """Verify a TOTP code with time window tolerance"""
        if not secret or not code:
            return False
        
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=window)
        except Exception:
            return False
    
    @staticmethod
    def check_rate_limit(user, max_failures=5, lockout_minutes=30):
        """Check if user is rate limited for TOTP attempts"""
        if user.totp_failure_count >= max_failures:
            if user.last_totp_failure:
                lockout_until = user.last_totp_failure + timedelta(minutes=lockout_minutes)
                if timezone.now() < lockout_until:
                    return False, lockout_until
                else:
                    user.totp_failure_count = 0
                    user.last_totp_failure = None
                    user.save()
        
        return True, None
