from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.conf import settings
from .utils import decode_token, verify_token
import logging

logger = logging.getLogger(__name__)

class AntiDDoSMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith('/admin/'):
            return None
            
        if request.path.startswith('/anti_ddos/'): 
            return None
            
        token = request.COOKIES.get('hmac_token')
        logger.info(f"AntiDDoS Middleware: path={request.path}, token_present={bool(token)}")
        
        if request.session.get('captcha_passed'):
            return None
            
        if token:
            logger.info(f"AntiDDoS Middleware: token_length={len(token)}")
            decoded_token = decode_token(token)
            logger.info(f"AntiDDoS Middleware: decoded_token={bool(decoded_token)}")
            
            if decoded_token:
                original_remaining = decoded_token.remaining
                verification_result = verify_token(decoded_token)
                logger.info(f"AntiDDoS Middleware: verification_result={verification_result}")
                
                if verification_result:
                    logger.info("AntiDDoS Middleware: Token verified successfully - allowing request")
                    if decoded_token.remaining != original_remaining:
                        from .utils import serialize_token
                        updated_token_str = serialize_token(decoded_token)
                        request._updated_hmac_token = updated_token_str
                    return None
                else:
                    logger.warning("AntiDDoS Middleware: Token verification failed")
            else:
                logger.warning("AntiDDoS Middleware: Token decoding failed")
        else:
            logger.info("AntiDDoS Middleware: No token present")
            
        logger.info("AntiDDoS Middleware: Redirecting to challenge")
        return redirect('anti_ddos:challenge')
    
    def process_response(self, request, response):
        if hasattr(request, '_updated_hmac_token'):
            response.set_cookie('hmac_token', request._updated_hmac_token,
                              max_age=7200, httponly=True, secure=False,
                              domain=None, path='/')
            logger.info("AntiDDoS Middleware: Updated token cookie in response")
        return response
