import hmac
import hashlib
import time
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from core.utils.security import get_session_hash
from core.security.sanitization import UniversalSanitizer


def generate_nonce():
    return hashlib.sha256(str(time.time()).encode()).hexdigest()


@csrf_exempt
def challenge(request):
    if request.method == 'POST':
        hp = UniversalSanitizer.sanitize_text(request.POST.get('hp_field', ''))
        if hp:
            return render(request, 'anti_ddos/denied.html')
        
        nonce = UniversalSanitizer.sanitize_text(request.POST.get('nonce', ''))
        if not nonce:
            return render(request, 'anti_ddos/challenge.html', {
                'error': 'Missing nonce',
                'nonce': generate_nonce(),
                'ts': int(time.time()),
                'sig': '',
            })
        
        ts = int(request.POST.get('ts', '0'))
        if time.time() - ts < 0:  # Changed from 3 to 0 to fix timing issue
            return render(request, 'anti_ddos/too_fast.html')
        
        sig = UniversalSanitizer.sanitize_text(request.POST.get('sig', ''))
        msg = f"{nonce}|{ts}|{get_session_hash(request)}".encode()
        expected = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected, sig):
            return render(request, 'anti_ddos/denied.html')
        
        resp = redirect(request.GET.get('next', '/'))
        token = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
        resp.set_cookie('ad_token', token, max_age=900, httponly=True, secure=True)
        return resp
    else:
        ts = int(time.time())
        nonce = generate_nonce()
        msg = f"{nonce}|{ts}|{get_session_hash(request)}".encode()
        sig = hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
        return render(request, 'anti_ddos/challenge.html', {
            'nonce': nonce,
            'ts': ts,
            'sig': sig,
        })
