import time
import secrets
import hashlib
import logging
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin
from config.security_config import SECRET_MANAGER

logger = logging.getLogger('session.security')


class SecureSessionManager:
    """Enterprise-grade session security management"""
    
    def __init__(self):
        self.session_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 1800)
        self.rotation_interval = getattr(settings, 'SECURITY_SETTINGS', {}).get('SESSION_ROTATION_INTERVAL', 600)
        self.max_sessions_per_user = 3
    
    def create_session(self, request, user):
        """Create a new secure session"""
        session_id = self.generate_session_id()
        session_data = {
            'user_id': user.id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'last_rotation': time.time(),
            'csrf_token': secrets.token_urlsafe(32),
            'integrity_hash': None,
            'user_agent_hash': self._hash_user_agent(request),
            'session_version': 1
        }
        
        # Generate integrity hash
        session_data['integrity_hash'] = self._generate_integrity_hash(session_data)
        
        # Store in cache with encryption
        encrypted_data = SECRET_MANAGER.encrypt_sensitive_data(str(session_data))
        cache.set(f'secure_session:{session_id}', encrypted_data, timeout=self.session_timeout)
        
        # Track user sessions (limit concurrent sessions)
        self._track_user_session(user.id, session_id)
        
        # Set secure session in Django session
        request.session['secure_session_id'] = session_id
        request.session['session_created'] = time.time()
        request.session.set_expiry(self.session_timeout)
        
        logger.info(f"Secure session created for user {user.id}")
        return session_id
    
    def validate_session(self, request):
        """Validate session security and integrity"""
        session_id = request.session.get('secure_session_id')
        if not session_id:
            return False, "No secure session ID"
        
        # Retrieve encrypted session data
        cache_key = f'secure_session:{session_id}'
        encrypted_data = cache.get(cache_key)
        
        if not encrypted_data:
            return False, "Session not found or expired"
        
        try:
            # Decrypt session data
            session_data_str = SECRET_MANAGER.decrypt_sensitive_data(encrypted_data)
            import json
            session_data = json.loads(session_data_str)
        except Exception as e:
            logger.error(f"Failed to decrypt session data: {e}")
            return False, "Session data corrupted"
        
        # Verify integrity
        stored_hash = session_data.get('integrity_hash')
        session_data_copy = session_data.copy()
        session_data_copy.pop('integrity_hash', None)
        expected_hash = self._generate_integrity_hash(session_data_copy)
        
        if not SECRET_MANAGER.secure_compare(stored_hash, expected_hash):
            logger.warning(f"Session integrity check failed for session {session_id}")
            return False, "Session integrity compromised"
        
        # Check session age
        current_time = time.time()
        session_age = current_time - session_data['created_at']
        
        if session_age > self.session_timeout:
            logger.info(f"Session {session_id} expired due to age")
            return False, "Session expired"
        
        # Check activity timeout
        inactivity_time = current_time - session_data['last_activity']
        if inactivity_time > self.session_timeout:
            logger.info(f"Session {session_id} expired due to inactivity")
            return False, "Session inactive too long"
        
        # Validate user agent consistency (fingerprinting protection for legitimate users)
        current_ua_hash = self._hash_user_agent(request)
        if not SECRET_MANAGER.secure_compare(session_data['user_agent_hash'], current_ua_hash):
            logger.warning(f"User agent mismatch for session {session_id}")
            return False, "Session security violation"
        
        # Check if session needs rotation
        time_since_rotation = current_time - session_data['last_rotation']
        if time_since_rotation > self.rotation_interval:
            self._rotate_session(request, session_id, session_data)
        
        # Update last activity
        session_data['last_activity'] = current_time
        session_data['integrity_hash'] = self._generate_integrity_hash(session_data)
        
        # Re-encrypt and store
        encrypted_data = SECRET_MANAGER.encrypt_sensitive_data(str(session_data))
        cache.set(cache_key, encrypted_data, timeout=self.session_timeout)
        
        return True, "Session valid"
    
    def destroy_session(self, request, session_id=None):
        """Securely destroy session"""
        if not session_id:
            session_id = request.session.get('secure_session_id')
        
        if session_id:
            # Remove from cache
            cache.delete(f'secure_session:{session_id}')
            
            # Remove from user session tracking
            if hasattr(request, 'user') and request.user.is_authenticated:
                self._remove_user_session(request.user.id, session_id)
            
            # Clear Django session
            request.session.flush()
            
            logger.info(f"Session {session_id} destroyed")
    
    def generate_session_id(self):
        """Generate cryptographically secure session ID"""
        return SECRET_MANAGER.generate_secure_token(64)
    
    def _generate_integrity_hash(self, session_data):
        """Generate integrity hash for session data"""
        # Create deterministic string representation
        data_str = f"{session_data['user_id']}:{session_data['created_at']}:{session_data['csrf_token']}:{session_data['user_agent_hash']}"
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _hash_user_agent(self, request):
        """Hash user agent for fingerprinting"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return hashlib.sha256(user_agent.encode()).hexdigest()[:16]
    
    def _rotate_session(self, request, old_session_id, session_data):
        """Rotate session ID for enhanced security"""
        new_session_id = self.generate_session_id()
        
        # Update session data
        session_data['last_rotation'] = time.time()
        session_data['session_version'] += 1
        session_data['integrity_hash'] = self._generate_integrity_hash(session_data)
        
        # Store with new session ID
        encrypted_data = SECRET_MANAGER.encrypt_sensitive_data(str(session_data))
        cache.set(f'secure_session:{new_session_id}', encrypted_data, timeout=self.session_timeout)
        
        # Remove old session
        cache.delete(f'secure_session:{old_session_id}')
        
        # Update Django session
        request.session['secure_session_id'] = new_session_id
        
        # Update user session tracking
        if hasattr(request, 'user') and request.user.is_authenticated:
            self._remove_user_session(request.user.id, old_session_id)
            self._track_user_session(request.user.id, new_session_id)
        
        logger.info(f"Session rotated from {old_session_id} to {new_session_id}")
    
    def _track_user_session(self, user_id, session_id):
        """Track active sessions per user"""
        cache_key = f'user_sessions:{user_id}'
        sessions = cache.get(cache_key, [])
        
        # Add new session
        sessions.append({
            'session_id': session_id,
            'created_at': time.time()
        })
        
        # Limit concurrent sessions
        if len(sessions) > self.max_sessions_per_user:
            # Remove oldest session
            oldest = min(sessions, key=lambda x: x['created_at'])
            cache.delete(f'secure_session:{oldest["session_id"]}')
            sessions = [s for s in sessions if s['session_id'] != oldest['session_id']]
            logger.info(f"Removed oldest session for user {user_id} due to limit")
        
        cache.set(cache_key, sessions, timeout=self.session_timeout * 2)
    
    def _remove_user_session(self, user_id, session_id):
        """Remove session from user tracking"""
        cache_key = f'user_sessions:{user_id}'
        sessions = cache.get(cache_key, [])
        sessions = [s for s in sessions if s['session_id'] != session_id]
        cache.set(cache_key, sessions, timeout=self.session_timeout * 2)
    
    def get_user_sessions(self, user_id):
        """Get all active sessions for a user"""
        cache_key = f'user_sessions:{user_id}'
        return cache.get(cache_key, [])
    
    def terminate_all_user_sessions(self, user_id):
        """Terminate all sessions for a user"""
        sessions = self.get_user_sessions(user_id)
        
        for session in sessions:
            cache.delete(f'secure_session:{session["session_id"]}')
        
        cache.delete(f'user_sessions:{user_id}')
        logger.info(f"Terminated all sessions for user {user_id}")


class SecureSessionMiddleware(MiddlewareMixin):
    """Middleware for enhanced session security"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.session_manager = SecureSessionManager()
    
    def process_request(self, request):
        """Process incoming request for session validation"""
        # Skip for static files and certain paths
        skip_paths = ['/static/', '/media/', '/favicon.ico', '/robots.txt']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Only validate sessions for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        # Validate session
        is_valid, reason = self.session_manager.validate_session(request)
        
        if not is_valid:
            logger.warning(f"Session validation failed for user {request.user.id}: {reason}")
            
            # Destroy compromised session
            self.session_manager.destroy_session(request)
            
            # Force logout
            logout(request)
            
            # Redirect to login
            return HttpResponseRedirect(reverse('accounts:login'))
        
        return None
    
    def process_response(self, request, response):
        """Process response to add security headers"""
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy for enhanced protection
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "media-src 'none'; "
            "frame-src 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        return response


# Singleton instance
SESSION_MANAGER = SecureSessionManager()