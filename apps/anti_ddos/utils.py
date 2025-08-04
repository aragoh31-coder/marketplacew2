import pickle, base64, json, hmac, hashlib, time
import random
import struct

HMAC_KEY_LEN = 32
HMAC_SIG_LEN = 32
MIN_SOLVE_TIME = 0
MAX_SOLVE_TIME = 300
TOKEN_LIFETIME = 7200
HONEYPOT_COUNT = 5

hmac_key = None
last_key_rotation = 0

def hmac_init():
    global hmac_key, last_key_rotation
    now = time.time()
    if not last_key_rotation or now - last_key_rotation > 86400:
        hmac_key = random.randbytes(HMAC_KEY_LEN)
        last_key_rotation = now

def hmac_sign(data):
    global hmac_key
    hmac_init()
    if hmac_key is None:
        hmac_key = random.randbytes(HMAC_KEY_LEN)
    
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True).encode()
    elif isinstance(data, str):
        data = data.encode()
    return hmac.new(hmac_key, data, hashlib.sha256).digest()

class HMACChallenge:
    def __init__(self, difficulty=0):
        hmac_init()
        self.id = random.randbytes(16)
        self.created = time.time()
        self.mint = self.created + MIN_SOLVE_TIME
        self.maxt = self.created + MAX_SOLVE_TIME
        self.difficulty = difficulty
        
        if difficulty < 2:
            self.a = random.randint(1, 50)
            self.b = random.randint(1, 50)
            self.expected = self.a + self.b
            self.operation = '+'
        else:
            self.a = random.randint(1, 10)
            self.b = random.randint(1, 10)
            self.expected = self.a * self.b
            self.operation = '×'
            
        self.honeypots = []
        for i in range(HONEYPOT_COUNT):
            if hmac_key is not None and i < len(hmac_key):
                self.honeypots.append(f"hp{i:02d}_{hmac_key[i]:02x}")
            else:
                self.honeypots.append(f"hp{i:02d}_00")
            
        challenge_data = {
            'id': base64.b64encode(self.id).decode(),
            'created': self.created,
            'mint': self.mint,
            'maxt': self.maxt,
            'a': self.a,
            'b': self.b,
            'expected': self.expected,
            'difficulty': self.difficulty,
            'honeypots': self.honeypots
        }
        self.hmac_sig = hmac_sign(challenge_data)

class HMACToken:
    def __init__(self):
        hmac_init()
        self.magic = 0x544F5248  # "TORH"
        self.issued = time.time()
        self.expires = self.issued + TOKEN_LIFETIME
        self.remaining = 500
        
        token_data = {
            'magic': self.magic,
            'issued': self.issued,
            'expires': self.expires,
            'remaining': self.remaining
        }
        self.sig = hmac_sign(token_data)

def serialize_token(token):
    obj = {
        'magic': token.magic,
        'issued': token.issued,
        'expires': token.expires,
        'remaining': token.remaining,
        'sig': base64.b64encode(token.sig).decode(),
    }
    return base64.b64encode(json.dumps(obj).encode()).decode()

def decode_token(token_str):
    try:
        obj = json.loads(base64.b64decode(token_str).decode())
        
        class TokenObj:
            def __init__(self):
                self.magic = obj['magic']
                self.issued = obj['issued']
                self.expires = obj['expires']
                self.remaining = obj['remaining']
                self.sig = base64.b64decode(obj['sig'])
        
        return TokenObj()
    except:
        return None

def verify_token(token):
    if not token:
        return False
        
    now = time.time()
    if token.magic != 0x544F5248 or now > token.expires or token.remaining == 0:
        return False
    
    token_data = {
        'magic': token.magic,
        'issued': token.issued,
        'expires': token.expires,
        'remaining': token.remaining
    }
    expected_sig = hmac_sign(token_data)
    
    if not hmac.compare_digest(expected_sig, token.sig):
        return False
    
    token.remaining -= 1
    token_data['remaining'] = token.remaining
    token.sig = hmac_sign(token_data)
    
    return True

def serialize_challenge(challenge):
    challenge_data = {
        'id': base64.b64encode(challenge.id).decode(),
        'created': challenge.created,
        'mint': challenge.mint,
        'maxt': challenge.maxt,
        'a': challenge.a,
        'b': challenge.b,
        'expected': challenge.expected,
        'operation': challenge.operation,
        'difficulty': challenge.difficulty,
        'honeypots': challenge.honeypots,
        'hmac_sig': base64.b64encode(challenge.hmac_sig).decode()
    }
    return base64.b64encode(json.dumps(challenge_data).encode()).decode()

def decode_challenge(challenge_str):
    try:
        obj = json.loads(base64.b64decode(challenge_str).decode())
        
        class ChallengeObj:
            def __init__(self):
                self.id = base64.b64decode(obj['id'])
                self.created = obj['created']
                self.mint = obj['mint']
                self.maxt = obj['maxt']
                self.a = obj['a']
                self.b = obj['b']
                self.expected = obj['expected']
                self.operation = obj.get('operation', '+')
                self.difficulty = obj['difficulty']
                self.honeypots = obj['honeypots']
                self.hmac_sig = base64.b64decode(obj['hmac_sig'])
        
        return ChallengeObj()
    except:
        return None

def create_challenge(difficulty=0):
    return HMACChallenge(difficulty)

def verify_challenge(challenge, answer, start_time, honeypot_values):
    if not challenge:
        return False
        
    now = time.time()
    
    if now > challenge.maxt:
        return False
    
    if now < challenge.mint:
        return False
    
    for hp_val in honeypot_values:
        if hp_val and hp_val.strip():
            return False
    
    challenge_data = {
        'id': base64.b64encode(challenge.id).decode(),
        'created': challenge.created,
        'mint': challenge.mint,
        'maxt': challenge.maxt,
        'a': challenge.a,
        'b': challenge.b,
        'expected': challenge.expected,
        'difficulty': challenge.difficulty,
        'honeypots': challenge.honeypots
    }
    expected_sig = hmac_sign(challenge_data)
    
    if not hmac.compare_digest(expected_sig, challenge.hmac_sig):
        return False
    
    try:
        user_answer = int(answer)
        return user_answer == challenge.expected
    except (ValueError, TypeError):
        return False

def issue_token():
    return HMACToken()
