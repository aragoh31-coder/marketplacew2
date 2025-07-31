from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .utils import create_challenge, serialize_challenge, decode_challenge, verify_challenge, issue_token, serialize_token
import time
import logging

logger = logging.getLogger(__name__)

def challenge_view(request):
    diff = 0  # dynamic adjustment possible
    c = create_challenge(diff)
    data = serialize_challenge(c)
    return render(request, 'anti_ddos/challenge.html', {
        'challenge_data': data,
        'challenge': c,
        'now_ts': int(time.time()),
    })

@csrf_exempt
def verify_view(request):
    try:
        data = request.POST.get('challenge_data')
        ans = request.POST.get('answer')
        start_time_str = request.POST.get('start_time', '')
        
        logger.info(f"HMAC Verify: data={bool(data)}, ans={ans}, start_time={start_time_str}")
        
        if not data or not ans or not start_time_str:
            logger.warning("HMAC Verify: Missing required fields")
            return redirect('anti_ddos:challenge')
            
        start = int(start_time_str)
        hps = [request.POST.get(f'hp{i}', '') for i in range(5)]
        c = decode_challenge(data)
        
        if not c:
            logger.error("HMAC Verify: Failed to decode challenge")
            return redirect('anti_ddos:challenge')
        
        logger.info(f"HMAC Verify: Challenge decoded - a={c.a}, b={c.b}, expected={c.expected}")
        
        current_time = time.time()
        logger.info(f"HMAC Verify: Time check - current={current_time}, mint={c.mint}, maxt={c.maxt}")
        
        if current_time > c.maxt:
            logger.warning("HMAC Verify: Too late - challenge expired")
            return redirect('anti_ddos:challenge')
        
        if current_time < c.mint:
            logger.warning("HMAC Verify: Too early - minimum solve time not reached")
            return redirect('anti_ddos:challenge')
        
        verification_start = start
        logger.info(f"HMAC Verify: Using verification_start={verification_start}")
        
        verification_result = verify_challenge(c, ans, verification_start, hps)
        logger.info(f"HMAC Verify: Verification result={verification_result}")
        
        if verification_result:
            logger.info("HMAC Verify: Challenge verified successfully - issuing token")
            t = issue_token()
            token_str = serialize_token(t)
            logger.info(f"HMAC Verify: Token issued, length={len(token_str)}")
            
            request.session['captcha_passed'] = True
            request.session.save()
            
            resp = redirect('/')
            resp.set_cookie('hmac_token', token_str,
                            max_age=7200, httponly=True, secure=False, 
                            domain=None, path='/')
            logger.info("HMAC Verify: Cookie set, redirecting to main site")
            return resp
        else:
            logger.warning("HMAC Verify: Challenge verification failed")
            
    except (ValueError, TypeError) as e:
        logger.error(f"HMAC Verify: Exception - {e}")
    
    logger.info("HMAC Verify: Redirecting back to challenge")
    return redirect('anti_ddos:challenge')
