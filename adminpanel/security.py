import hashlib
import time
import secrets
from django.core.cache import cache
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class AdminSecurityManager:
    """Enhanced security manager for admin operations"""
    
    def __init__(self):
        self.max_failed_attempts = 3
        self.lockout_duration = 1800  # 30 minutes
        self.session_timeout = 3600   # 1 hour
    
    def check_admin_access(self, user, request):
        """Check if user has admin access and is not locked out"""
        if not user.is_staff:
            return False, "Not authorized for admin access"
        
        lockout_key = f"admin_lockout:{user.id}"
        if cache.get(lockout_key):
            return False, "Account temporarily locked due to failed attempts"
        
        return True, "OK"
    
    def record_failed_attempt(self, user, attempt_type="login"):
        """Record failed admin attempt"""
        cache_key = f"admin_failed:{user.id}:{attempt_type}"
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, self.lockout_duration)
        
        if attempts >= self.max_failed_attempts:
            lockout_key = f"admin_lockout:{user.id}"
            cache.set(lockout_key, True, self.lockout_duration)
            
            self._log_security_event(user, "admin_lockout", {
                'attempt_type': attempt_type,
                'failed_attempts': attempts
            })
        
        return attempts
    
    def clear_failed_attempts(self, user, attempt_type="login"):
        """Clear failed attempts after successful auth"""
        cache_key = f"admin_failed:{user.id}:{attempt_type}"
        cache.delete(cache_key)
    
    def generate_pgp_challenge(self, user):
        """Generate PGP challenge for admin verification"""
        challenge_data = {
            'timestamp': int(time.time()),
            'user_id': user.id,
            'nonce': secrets.token_urlsafe(16),
            'action': 'admin_verification'
        }
        
        challenge_string = f"ADMIN-VERIFY:{challenge_data['timestamp']}:{challenge_data['nonce']}"
        challenge_hash = hashlib.sha256(challenge_string.encode()).hexdigest()[:16]
        
        cache_key = f"admin_pgp_challenge:{user.id}"
        cache.set(cache_key, {
            'challenge': challenge_string,
            'hash': challenge_hash,
            'timestamp': challenge_data['timestamp']
        }, 600)  # 10 minutes
        
        return challenge_string, challenge_hash
    
    def verify_pgp_challenge(self, user, decrypted_response):
        """Verify PGP challenge response"""
        cache_key = f"admin_pgp_challenge:{user.id}"
        challenge_data = cache.get(cache_key)
        
        if not challenge_data:
            return False, "Challenge expired or not found"
        
        if time.time() - challenge_data['timestamp'] > 600:
            cache.delete(cache_key)
            return False, "Challenge expired"
        
        if decrypted_response.strip() == challenge_data['challenge']:
            cache.delete(cache_key)
            return True, "Challenge verified"
        
        return False, "Invalid challenge response"
    
    def create_admin_session(self, user, request):
        """Create secure admin session"""
        session_token = secrets.token_urlsafe(32)
        session_data = {
            'user_id': user.id,
            'created_at': time.time(),
            'ip_hash': self._hash_ip(request),
            'user_agent_hash': hashlib.sha256(
                request.META.get('HTTP_USER_AGENT', '').encode()
            ).hexdigest()[:16]
        }
        
        cache_key = f"admin_session:{session_token}"
        cache.set(cache_key, session_data, self.session_timeout)
        
        request.session['admin_session_token'] = session_token
        request.session['admin_authenticated'] = True
        request.session['admin_auth_time'] = time.time()
        
        return session_token
    
    def validate_admin_session(self, request):
        """Validate admin session"""
        session_token = request.session.get('admin_session_token')
        if not session_token:
            return False, "No admin session"
        
        cache_key = f"admin_session:{session_token}"
        session_data = cache.get(cache_key)
        
        if not session_data:
            return False, "Session expired"
        
        if time.time() - session_data['created_at'] > self.session_timeout:
            cache.delete(cache_key)
            return False, "Session timeout"
        
        current_ua_hash = hashlib.sha256(
            request.META.get('HTTP_USER_AGENT', '').encode()
        ).hexdigest()[:16]
        
        if current_ua_hash != session_data['user_agent_hash']:
            cache.delete(cache_key)
            return False, "Session inconsistency detected"
        
        return True, "Session valid"
    
    def _hash_ip(self, request):
        """Hash IP for session validation without logging actual IP"""
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
    
    def _log_security_event(self, user, event_type, details):
        """Log security events"""
        try:
            from wallets.models import AuditLog
            AuditLog.objects.create(
                user=user,
                action='admin_security_event',
                ip_address='privacy_protected',
                user_agent='admin_system',
                details={
                    'event_type': event_type,
                    **details
                },
                flagged=True,
                risk_score=80
            )
        except:
            pass  # Don't break on logging errors


class TripleAuthenticator:
    """Triple authentication system for admin access"""
    
    def __init__(self):
        self.security_manager = AdminSecurityManager()
    
    def start_authentication(self, user, request):
        """Start triple authentication process"""
        can_access, message = self.security_manager.check_admin_access(user, request)
        if not can_access:
            return False, message, None
        
        auth_state = {
            'user_id': user.id,
            'step': 1,
            'completed_steps': [],
            'started_at': time.time()
        }
        
        auth_token = secrets.token_urlsafe(32)
        cache_key = f"admin_triple_auth:{auth_token}"
        cache.set(cache_key, auth_state, 1800)  # 30 minutes
        
        return True, "Authentication started", auth_token
    
    def verify_step(self, auth_token, step, verification_data):
        """Verify authentication step"""
        cache_key = f"admin_triple_auth:{auth_token}"
        auth_state = cache.get(cache_key)
        
        if not auth_state:
            return False, "Authentication session expired", None
        
        if time.time() - auth_state['started_at'] > 1800:
            cache.delete(cache_key)
            return False, "Authentication timeout", None
        
        success = False
        message = ""
        
        if step == 1:  # Primary password
            success, message = self._verify_primary_password(
                auth_state['user_id'], 
                verification_data.get('password')
            )
        elif step == 2:  # Secondary password
            success, message = self._verify_secondary_password(
                auth_state['user_id'], 
                verification_data.get('secondary_password')
            )
        elif step == 3:  # PGP verification
            success, message = self._verify_pgp_challenge(
                auth_state['user_id'], 
                verification_data.get('pgp_response')
            )
        
        if success:
            auth_state['completed_steps'].append(step)
            auth_state['step'] = step + 1
            cache.set(cache_key, auth_state, 1800)
            
            if len(auth_state['completed_steps']) == 3:
                return True, "Authentication complete", auth_state
        
        return success, message, auth_state
    
    def _verify_primary_password(self, user_id, password):
        """Verify primary password"""
        try:
            user = User.objects.get(id=user_id)
            if user.check_password(password):
                return True, "Primary password verified"
            return False, "Invalid primary password"
        except User.DoesNotExist:
            return False, "User not found"
    
    def _verify_secondary_password(self, user_id, secondary_password):
        """Verify secondary password"""
        try:
            from .models import AdminProfile
            admin_profile = AdminProfile.objects.get(user_id=user_id)
            if admin_profile.check_secondary_password(secondary_password):
                return True, "Secondary password verified"
            return False, "Invalid secondary password"
        except:
            return False, "Secondary password not configured"
    
    def _verify_pgp_challenge(self, user_id, pgp_response):
        """Verify PGP challenge"""
        try:
            user = User.objects.get(id=user_id)
            return self.security_manager.verify_pgp_challenge(user, pgp_response)
        except User.DoesNotExist:
            return False, "User not found"
