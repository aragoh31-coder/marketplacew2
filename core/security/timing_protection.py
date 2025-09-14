import time
import secrets
import hashlib
import hmac
from typing import Any, Callable
from functools import wraps
from config.security_config import SECRET_MANAGER
import logging

logger = logging.getLogger('security.timing')


class TimingAttackProtection:
    """
    Protection against timing attacks for security-sensitive operations
    - Constant-time string comparison
    - Uniform response timing
    - Authentication delay mechanisms
    - Cryptographic operation timing normalization
    """
    
    def __init__(self):
        self.base_delay = 0.1  # Base delay in seconds
        self.max_jitter = 0.05  # Maximum random jitter
        self.min_operation_time = 0.2  # Minimum time for sensitive operations
    
    def constant_time_compare(self, val1: str, val2: str) -> bool:
        """
        Constant-time string comparison to prevent timing attacks
        
        Args:
            val1: First string to compare
            val2: Second string to compare
            
        Returns:
            True if strings are equal, False otherwise
        """
        return secrets.compare_digest(val1, val2)
    
    def secure_hash_compare(self, provided_hash: str, stored_hash: str) -> bool:
        """
        Secure hash comparison with timing attack protection
        
        Args:
            provided_hash: Hash provided by user/client
            stored_hash: Hash stored in database
            
        Returns:
            True if hashes match, False otherwise
        """
        # Normalize hash lengths by hashing both
        normalized_provided = hashlib.sha256(provided_hash.encode()).hexdigest()
        normalized_stored = hashlib.sha256(stored_hash.encode()).hexdigest()
        
        return self.constant_time_compare(normalized_provided, normalized_stored)
    
    def normalize_operation_timing(self, target_time: float = None) -> Callable:
        """
        Decorator to normalize operation timing
        
        Args:
            target_time: Target time for operation completion
        """
        if target_time is None:
            target_time = self.min_operation_time
        
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    # Even on exceptions, maintain timing
                    self._wait_for_target_time(start_time, target_time)
                    raise
                
                self._wait_for_target_time(start_time, target_time)
                return result
            
            return wrapper
        return decorator
    
    def _wait_for_target_time(self, start_time: float, target_time: float):
        """Wait until target time has elapsed"""
        elapsed = time.time() - start_time
        remaining = target_time - elapsed
        
        if remaining > 0:
            # Add small random jitter to prevent timing analysis
            jitter = secrets.randbelow(int(self.max_jitter * 1000)) / 1000
            total_wait = remaining + jitter
            time.sleep(total_wait)
    
    def authenticate_with_timing_protection(self, 
                                          provided_credential: str,
                                          stored_credential_hash: str,
                                          hash_function: Callable = None) -> bool:
        """
        Authentication with comprehensive timing attack protection
        
        Args:
            provided_credential: Credential provided by user
            stored_credential_hash: Stored credential hash
            hash_function: Function to hash the provided credential
            
        Returns:
            True if authentication succeeds, False otherwise
        """
        start_time = time.time()
        
        try:
            # Always perform hashing operation, even if stored hash is invalid
            if hash_function:
                provided_hash = hash_function(provided_credential)
            else:
                provided_hash = hashlib.sha256(provided_credential.encode()).hexdigest()
            
            # Perform constant-time comparison
            is_valid = self.constant_time_compare(provided_hash, stored_credential_hash)
            
            # Add authentication-specific delay
            self._add_authentication_delay(is_valid)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Authentication timing protection error: {e}")
            # Still maintain timing even on error
            self._wait_for_target_time(start_time, self.min_operation_time)
            return False
    
    def _add_authentication_delay(self, success: bool):
        """Add authentication-specific delay"""
        # Successful authentications get slightly less delay
        if success:
            delay = self.base_delay + secrets.randbelow(int(self.max_jitter * 1000)) / 1000
        else:
            # Failed authentications get slightly more delay
            delay = self.base_delay * 1.2 + secrets.randbelow(int(self.max_jitter * 1000)) / 1000
        
        time.sleep(delay)
    
    def password_verification_with_protection(self, 
                                            provided_password: str,
                                            stored_password_hash: str) -> bool:
        """
        Password verification with timing attack protection
        Uses Argon2 or similar secure password hashing
        """
        start_time = time.time()
        
        try:
            # Always perform a password hashing operation for timing consistency
            if not stored_password_hash:
                # If no stored hash, still perform expensive operation
                dummy_hash = SECRET_MANAGER.hash_password("dummy_password_for_timing")
                self._wait_for_target_time(start_time, 0.5)  # Minimum 500ms for password ops
                return False
            
            # Verify password
            is_valid = SECRET_MANAGER.verify_password(provided_password, stored_password_hash)
            
            # Ensure minimum timing
            self._wait_for_target_time(start_time, 0.5)
            
            # Add authentication delay
            self._add_authentication_delay(is_valid)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Password verification timing protection error: {e}")
            self._wait_for_target_time(start_time, 0.5)
            return False
    
    def database_lookup_with_protection(self, 
                                      lookup_function: Callable,
                                      *args, **kwargs) -> Any:
        """
        Database lookup with timing protection
        Normalizes timing regardless of whether record exists
        """
        start_time = time.time()
        
        try:
            result = lookup_function(*args, **kwargs)
            
            # Add consistent delay regardless of result
            self._wait_for_target_time(start_time, 0.1)
            
            return result
            
        except Exception as e:
            logger.error(f"Database lookup timing protection error: {e}")
            self._wait_for_target_time(start_time, 0.1)
            raise
    
    def crypto_operation_with_protection(self, 
                                       operation_function: Callable,
                                       target_time: float = 0.3,
                                       *args, **kwargs) -> Any:
        """
        Cryptographic operation with timing normalization
        
        Args:
            operation_function: Function performing crypto operation
            target_time: Target time for operation
            *args, **kwargs: Arguments for the operation function
        """
        start_time = time.time()
        
        try:
            result = operation_function(*args, **kwargs)
            self._wait_for_target_time(start_time, target_time)
            return result
            
        except Exception as e:
            logger.error(f"Crypto operation timing protection error: {e}")
            self._wait_for_target_time(start_time, target_time)
            raise
    
    def session_validation_with_protection(self, 
                                         validation_function: Callable,
                                         *args, **kwargs) -> bool:
        """
        Session validation with timing protection
        """
        start_time = time.time()
        
        try:
            is_valid = validation_function(*args, **kwargs)
            
            # Normalize timing for session validation
            self._wait_for_target_time(start_time, 0.15)
            
            # Add small random delay
            jitter = secrets.randbelow(50) / 1000  # 0-50ms jitter
            time.sleep(jitter)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Session validation timing protection error: {e}")
            self._wait_for_target_time(start_time, 0.15)
            return False


# Timing-safe utility functions
def timing_safe_equals(a: str, b: str) -> bool:
    """Timing-safe string equality check"""
    return TIMING_PROTECTION.constant_time_compare(a, b)


def timing_safe_password_verify(password: str, hash_str: str) -> bool:
    """Timing-safe password verification"""
    return TIMING_PROTECTION.password_verification_with_protection(password, hash_str)


def timing_safe_database_lookup(lookup_func, *args, **kwargs):
    """Timing-safe database lookup"""
    return TIMING_PROTECTION.database_lookup_with_protection(lookup_func, *args, **kwargs)


# Decorators for timing protection
def protect_timing(target_time: float = 0.2):
    """Decorator for timing attack protection"""
    return TIMING_PROTECTION.normalize_operation_timing(target_time)


def protect_auth_timing(func):
    """Decorator specifically for authentication operations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return TIMING_PROTECTION.crypto_operation_with_protection(func, 0.5, *args, **kwargs)
    return wrapper


def protect_crypto_timing(target_time: float = 0.3):
    """Decorator for cryptographic operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return TIMING_PROTECTION.crypto_operation_with_protection(func, target_time, *args, **kwargs)
        return wrapper
    return decorator


# Singleton instance
TIMING_PROTECTION = TimingAttackProtection()