import hmac
import hashlib
import time
import random
import logging
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from core.utils.security import get_session_hash
from core.security.sanitization import UniversalSanitizer

logger = logging.getLogger(__name__)


def generate_nonce():
    return hashlib.sha256(str(time.time()).encode()).hexdigest()


@csrf_exempt
def challenge(request):
    """
    Handle the anti-DDoS challenge page with math CAPTCHA.
    """
    if request.method == 'POST':
        hp = UniversalSanitizer.sanitize_text(request.POST.get('hp_field', ''))
        if hp:
            logger.warning("Honeypot triggered")
            return render(request, 'anti_ddos/denied.html', status=403)
        
        submitted_answer = request.POST.get('math_answer', '').strip()
        correct_answer = request.session.get('math_answer')
        
        if not correct_answer or not submitted_answer:
            return render(request, 'anti_ddos/challenge.html', {
                'math_question': _generate_math_challenge(request),
                'error': 'Please solve the math problem.'
            })
        
        try:
            if int(submitted_answer) == int(correct_answer):
                request.session["ddos_passed"] = True
                next_url = request.GET.get("next", "/")
                
                response = redirect(next_url)
                session_hash = get_session_hash(request)
                token_data = f"verified|{session_hash}".encode()
                token = hmac.new(
                    settings.SECRET_KEY.encode(),
                    token_data,
                    hashlib.sha256
                ).hexdigest()
                
                response.set_cookie(
                    'ad_token',
                    token,
                    max_age=3600,
                    secure=not settings.DEBUG,
                    httponly=True,
                    samesite='Strict'
                )
                return response
            else:
                return render(request, 'anti_ddos/challenge.html', {
                    'math_question': _generate_math_challenge(request),
                    'error': 'Incorrect answer. Please try again.'
                })
        except (ValueError, TypeError):
            return render(request, 'anti_ddos/challenge.html', {
                'math_question': _generate_math_challenge(request),
                'error': 'Please enter a valid number.'
            })
    
    math_question = _generate_math_challenge(request)
    
    context = {
        "math_question": math_question,
    }
    
    return render(request, "anti_ddos/challenge.html", context)


def _generate_math_challenge(request):
    """Generate math challenge similar to NoJSCaptchaMixin"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(['+', '-', '*'])
    
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2}"
    elif operation == '-':
        answer = num1 - num2
        question = f"{num1} - {num2}"
    else:
        answer = num1 * num2
        question = f"{num1} × {num2}"
    
    request.session['math_answer'] = answer
    request.session['math_question'] = question
    return question
