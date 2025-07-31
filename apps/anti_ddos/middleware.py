from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.conf import settings
from .utils import decode_token, verify_token
import logging

logger = logging.getLogger(__name__)

class AntiDDoSMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/anti_ddos/'):
            return None
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith('/admin/'):
            return None
        if request.session.get('captcha_passed'):
            return None
        token = request.COOKIES.get('hmac_token')
        if token:
            try:
                if verify_token(decode_token(token)):
                    return None
            except:
                pass
        return redirect('anti_ddos:challenge')
