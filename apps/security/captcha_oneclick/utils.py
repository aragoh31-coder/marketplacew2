import io
import base64
import random
import math
import time
import secrets
import hashlib
import hmac
from PIL import Image, ImageDraw, ImageFilter
from django.conf import settings

SIZE, R = 200, 80
SEGS = 12
HMAC_SECRET = getattr(settings, 'CAPTCHA_HMAC_SECRET', b'marketplace-captcha-secret-key')
POW_DIFFICULTY = getattr(settings, 'POW_DIFFICULTY', 4)

def make_cut_circle(missing):
    """Generate cut-circle CAPTCHA image"""
    img = Image.new('RGBA', (SIZE, SIZE), (30,30,50,240))
    d   = ImageDraw.Draw(img)
    cx, cy = SIZE//2, SIZE//2

    d.ellipse([cx-R,cy-R, cx+R,cy+R], fill=(40,40,60,240), outline=(255,255,255,200), width=3)

    colors = [(255,120,120), (120,220,120), (120,120,255)]
    for i in range(SEGS):
        if i==missing: continue
        jitter = random.uniform(-2,2)
        start = (i*360/SEGS) + jitter
        end   = ((i+1)*360/SEGS) - jitter
        d.pieslice([cx-R,cy-R, cx+R,cy+R], start, end, fill=random.choice(colors), outline=(255,255,255,150), width=2)

    gloss = Image.new('RGBA', (SIZE,SIZE), (255,255,255,0))
    gd   = ImageDraw.Draw(gloss)
    gd.ellipse([cx-R, cy-R-10, cx+R, cy+R-40], fill=(255,255,255,30))
    img = Image.alpha_composite(img, gloss)
    img = img.filter(ImageFilter.GaussianBlur(0.5))

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), missing

def generate_hmac_token(answer, timestamp):
    """Generate HMAC token for CAPTCHA answer"""
    message = f"{answer}:{timestamp}".encode()
    return hmac.new(HMAC_SECRET, message, hashlib.sha256).hexdigest()

def validate_hmac_token(token, answer, timestamp):
    """Validate HMAC token"""
    expected = generate_hmac_token(answer, timestamp)
    return hmac.compare_digest(token, expected)

def generate_pow_challenge():
    """Generate optional PoW challenge"""
    challenge = secrets.token_hex(16)
    return challenge

def validate_pow(challenge, nonce, difficulty=POW_DIFFICULTY):
    """Validate PoW solution (optional)"""
    if not challenge or not nonce:
        return True
    
    hash_input = f"{challenge}{nonce}".encode()
    hash_result = hashlib.sha256(hash_input).hexdigest()
    return hash_result.startswith('0' * difficulty)

def generate_captcha_with_tokens():
    """Generate CAPTCHA with HMAC token and optional PoW"""
    missing = random.randrange(SEGS)
    img_b64, _ = make_cut_circle(missing)
    timestamp = int(time.time())
    
    hmac_token = generate_hmac_token(missing, timestamp)
    pow_challenge = generate_pow_challenge()
    
    return {
        'image': img_b64,
        'answer': missing,
        'timestamp': timestamp,
        'hmac_token': hmac_token,
        'pow_challenge': pow_challenge,
        'segments': SEGS
    }

def validate_captcha_submission(user_answer, hmac_token, timestamp, pow_challenge=None, pow_nonce=None):
    """Validate complete CAPTCHA submission with HMAC and optional PoW"""
    if time.time() - timestamp > 120:
        return False, "CAPTCHA expired"
    
    if not validate_hmac_token(hmac_token, user_answer, timestamp):
        return False, "Invalid CAPTCHA token"
    
    if pow_challenge and not validate_pow(pow_challenge, pow_nonce):
        return False, "Invalid proof of work"
    
    return True, "Valid"

def generate_captcha():
    """Legacy compatibility function"""
    data = generate_captcha_with_tokens()
    return data['image'], data['answer'], data['hmac_token']

def validate_captcha(token, user_choice):
    """Legacy compatibility function"""
    try:
        choice, ts, sig = token.split(":")
        ts = int(ts)
    except ValueError:
        return False
    message = f"{choice}:{ts}".encode()
    expected_sig = hmac.new(HMAC_SECRET, message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return False
    if time.time() - ts > 120:
        return False
    return user_choice == choice
