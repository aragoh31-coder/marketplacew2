from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.core.cache import cache
import logging
import hashlib
import time

logger = logging.getLogger('security')

class OpenRestyIntegrationMiddleware(MiddlewareMixin):
    
    def process_request(self, request):
        openresty_filtered = request.META.get('HTTP_X_OPENRESTY_FILTERED')
        pow_verified = request.META.get('HTTP_X_POW_VERIFIED')
        client_fingerprint = request.META.get('HTTP_X_CLIENT_FINGERPRINT')
        client_ip = self.get_client_ip(request)
        
        if client_ip.startswith('172.18.') or client_ip.startswith('127.') or client_ip == 'localhost':
            logger.info(f"Internal network request from {client_ip} - allowing")
            return None
        
        if not openresty_filtered and not self._is_health_check(request):
            logger.warning(f"Direct access attempt bypassing OpenResty from {client_ip}")
            return HttpResponse("Access denied - requests must go through security layer", status=403)
        
        if pow_verified:
            logger.info(f"PoW verified request from {client_ip}")
            request.META['POW_VERIFIED'] = True
            cache.set(f"pow_verified:{client_fingerprint}", True, 3600)
        
        if client_fingerprint:
            request.META['CLIENT_FINGERPRINT'] = client_fingerprint
            self._track_request_metrics(client_fingerprint, request)
        
        return None
    
    def _is_health_check(self, request):
        health_paths = ['/health', '/openresty-status', '/pow-challenge', '/pow-verify']
        return any(request.path.startswith(path) for path in health_paths)
    
    def _track_request_metrics(self, fingerprint, request):
        current_time = int(time.time())
        minute_key = f"openresty_django_requests:{fingerprint}:{current_time // 60}"
        
        current_count = cache.get(minute_key, 0)
        cache.set(minute_key, current_count + 1, 60)
        
        if current_count > 15:
            logger.warning(f"High request rate from fingerprint {fingerprint}: {current_count + 1}/minute")
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip
    
    def process_response(self, request, response):
        response['X-Protected-By'] = 'OpenResty-AntiDDoS + Django-Security'
        response['X-Security-Layers'] = '7'
        
        if hasattr(request, 'META') and request.META.get('POW_VERIFIED'):
            response['X-PoW-Status'] = 'Verified'
        
        return response
