import random

CAPTCHA_CHOICES = [
    {"label": "Circle", "token": "circle"},
    {"label": "Half Circle", "token": "half_circle"},
    {"label": "Triangle", "token": "triangle"},
    {"label": "Square", "token": "square"}
]

def generate_captcha(session):
    correct_choice = random.choice(CAPTCHA_CHOICES)
    buttons = CAPTCHA_CHOICES[:]
    random.shuffle(buttons)
    session['captcha_expected'] = correct_choice['token']
    return correct_choice['label'], buttons

def validate_captcha(request):
    return request.POST.get('captcha_token') == request.session.get('captcha_expected')
