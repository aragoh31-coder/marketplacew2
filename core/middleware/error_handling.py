import logging
import traceback
from django.http import JsonResponse, HttpResponseServerError
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import hashlib

logger = logging.getLogger(__name__)

class EnhancedErrorHandlingMiddleware:
    """Enhanced error handling with security-focused error responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Process unhandled exceptions"""
        try:
            error_id = self._generate_error_id(request, exception)
            
            self._log_error(request, exception, error_id)
            
            if self._is_security_related_error(exception):
                self._handle_security_error(request, exception, error_id)
            
            if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
                return self._json_error_response(error_id)
            
            if settings.DEBUG:
                return None
            
            return self._render_error_page(request, exception, error_id)
            
        except Exception as e:
            logger.critical(f"Error in error handling middleware: {e}")
            return HttpResponseServerError("Internal server error")
    
    def _generate_error_id(self, request, exception):
        """Generate unique error ID for tracking"""
        error_data = f"{request.path}:{type(exception).__name__}:{timezone.now().isoformat()}"
        return hashlib.sha256(error_data.encode()).hexdigest()[:16]
    
    def _log_error(self, request, exception, error_id):
        """Log error with context"""
        try:
            user_info = 'anonymous'
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_info = f"user:{request.user.username}"
            
            error_context = {
                'error_id': error_id,
                'user': user_info,
                'path': request.path,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc()
            }
            
            logger.error(f"Unhandled exception [{error_id}]: {exception}", extra=error_context)
            
        except Exception as e:
            logger.critical(f"Failed to log error: {e}")
    
    def _is_security_related_error(self, exception):
        """Check if error is security-related"""
        security_exceptions = [
            'PermissionDenied',
            'SuspiciousOperation',
            'DisallowedHost',
            'ValidationError'
        ]
        
        return type(exception).__name__ in security_exceptions
    
    def _handle_security_error(self, request, exception, error_id):
        """Handle security-related errors"""
        try:
            client_ip = self._get_client_identifier(request)
            cache_key = f"security_errors:{client_ip}"
            
            error_count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, error_count, 3600)
            
            if error_count >= 5:
                logger.warning(f"Multiple security errors from {client_ip}: {error_count}")
                
                rate_limit_key = f"rate_limit:{client_ip}"
                cache.set(rate_limit_key, True, 1800)
            
        except Exception as e:
            logger.error(f"Failed to handle security error: {e}")
    
    def _get_client_identifier(self, request):
        """Get privacy-focused client identifier"""
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        
        identifier_data = f"{user_agent}:{accept_lang}"
        return hashlib.sha256(identifier_data.encode()).hexdigest()[:16]
    
    def _json_error_response(self, error_id):
        """Return JSON error response"""
        return JsonResponse({
            'error': 'Internal server error',
            'error_id': error_id,
            'message': 'An unexpected error occurred. Please try again later.'
        }, status=500)
    
    def _render_error_page(self, request, exception, error_id):
        """Render error page"""
        try:
            context = {
                'error_id': error_id,
                'error_type': type(exception).__name__,
                'support_contact': getattr(settings, 'SUPPORT_EMAIL', 'support@marketplace.onion')
            }
            
            if hasattr(exception, 'status_code'):
                status_code = exception.status_code
                template_name = f'errors/{status_code}.html'
            else:
                status_code = 500
                template_name = 'errors/500.html'
            
            return render(request, template_name, context, status=status_code)
            
        except Exception as e:
            logger.error(f"Failed to render error page: {e}")
            return HttpResponseServerError("Internal server error")

class SecurityResponseMiddleware:
    """Add security headers to responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if not getattr(settings, 'DEBUG', False):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            if request.is_secure():
                response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        response['Server'] = 'SecureMarketplace'
        
        return response
