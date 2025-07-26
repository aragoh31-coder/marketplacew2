from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.core.cache import cache
from django.utils import timezone
from apps.security.event_classifier import ThreatDetector, SecurityEventClassifier
import logging

logger = logging.getLogger('marketplace.security')

class ThreatDetectionMiddleware:
    """Middleware for real-time threat detection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        threats = ThreatDetector.detect_threats(request, getattr(request, 'user', None))
        
        if threats:
            self._handle_threats(request, threats)
        
        response = self.get_response(request)
        
        self._log_request_analysis(request, response, threats)
        
        return response
    
    def _handle_threats(self, request, threats):
        """Handle detected threats"""
        try:
            critical_threats = [t for t in threats if t['severity'] == 'critical']
            high_threats = [t for t in threats if t['severity'] == 'high']
            
            if critical_threats:
                self._handle_critical_threats(request, critical_threats)
            elif high_threats:
                self._handle_high_threats(request, high_threats)
            
            for threat in threats:
                logger.warning(f"Threat detected: {threat['type']}", extra={
                    'threat_data': threat,
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
                })
                
        except Exception as e:
            logger.error(f"Failed to handle threats: {e}")
    
    def _handle_critical_threats(self, request, threats):
        """Handle critical threats with immediate action"""
        try:
            client_id = self._get_client_identifier(request)
            
            cache.set(f"blocked_client:{client_id}", True, 3600)
            
            for threat in threats:
                SecurityEventClassifier.classify_event(
                    f"Critical threat detected: {threat['type']}",
                    context={'threat_data': threat, 'request_path': request.path}
                )
            
            logger.critical(f"Critical threats blocked client {client_id}: {[t['type'] for t in threats]}")
            
        except Exception as e:
            logger.error(f"Failed to handle critical threats: {e}")
    
    def _handle_high_threats(self, request, threats):
        """Handle high-severity threats with rate limiting"""
        try:
            client_id = self._get_client_identifier(request)
            
            cache_key = f"threat_rate_limit:{client_id}"
            threat_count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, threat_count, 1800)  # 30 minutes
            
            if threat_count >= 3:
                cache.set(f"temp_blocked:{client_id}", True, 900)
                logger.warning(f"Client {client_id} temporarily blocked due to repeated high threats")
            
        except Exception as e:
            logger.error(f"Failed to handle high threats: {e}")
    
    def _log_request_analysis(self, request, response, threats):
        """Log request analysis for monitoring"""
        try:
            if threats or response.status_code >= 400:
                analysis_data = {
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'threats_detected': len(threats),
                    'threat_types': [t['type'] for t in threats],
                    'user_authenticated': hasattr(request, 'user') and request.user.is_authenticated,
                    'timestamp': timezone.now().isoformat()
                }
                
                logger.info("Request analysis", extra=analysis_data)
                
        except Exception as e:
            logger.error(f"Failed to log request analysis: {e}")
    
    def _get_client_identifier(self, request):
        """Get client identifier for tracking"""
        import hashlib
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        
        identifier_data = f"{user_agent}:{accept_lang}"
        return hashlib.sha256(identifier_data.encode()).hexdigest()[:16]
    
    def process_request(self, request):
        """Check if client is blocked before processing request"""
        try:
            client_id = self._get_client_identifier(request)
            
            if cache.get(f"blocked_client:{client_id}"):
                logger.warning(f"Blocked client {client_id} attempted access to {request.path}")
                return HttpResponseForbidden("Access denied due to security policy")
            
            if cache.get(f"temp_blocked:{client_id}"):
                logger.info(f"Temporarily blocked client {client_id} attempted access")
                return render(request, 'security/temporarily_blocked.html', status=429)
            
        except Exception as e:
            logger.error(f"Failed to process request security check: {e}")
        
        return None
