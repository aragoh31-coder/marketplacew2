from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
import hashlib
import secrets
import time
import logging

logger = logging.getLogger('marketplace.security')


def generate_captcha_challenge():
    """Generate a math CAPTCHA challenge"""
    num1 = secrets.randbelow(10) + 1
    num2 = secrets.randbelow(10) + 1
    answer = num1 + num2
    
    challenge_data = {
        'question': f"{num1} + {num2}",
        'answer': answer,
        'timestamp': time.time()
    }
    
    return challenge_data


def validate_captcha_timing(timestamp, min_time=3, max_time=300):
    """Validate CAPTCHA timing to detect bots"""
    current_time = time.time()
    elapsed = current_time - timestamp
    
    if elapsed < min_time:
        return False, "Form submitted too quickly"
    
    if elapsed > max_time:
        return False, "Form expired"
    
    return True, "Valid timing"


def check_honeypot_field(value):
    """Check if honeypot field was filled (indicates bot)"""
    return value == "" or value is None


def generate_form_hash(user_id=None, timestamp=None):
    """Generate unique form hash for tracking"""
    if timestamp is None:
        timestamp = time.time()
    
    data = f"{user_id}:{timestamp}:{secrets.token_urlsafe(16)}"
    return hashlib.sha256(data.encode()).hexdigest()


def log_security_event(user, event_type, details=None, risk_score=0):
    """Log security events for audit trail"""
    from wallets.models import AuditLog
    
    try:
        AuditLog.objects.create(
            user=user,
            action=event_type,
            ip_address='privacy_protected',  # No IP logging for privacy
            user_agent='',
            details=details or {},
            risk_score=risk_score,
            flagged=risk_score >= 40
        )
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")


def rate_limit_key(identifier, action):
    """Generate cache key for rate limiting"""
    return f"rate_limit:{action}:{identifier}"


def check_rate_limit(identifier, action, limit=5, window=300):
    """Check if action is rate limited"""
    key = rate_limit_key(identifier, action)
    current_count = cache.get(key, 0)
    
    if current_count >= limit:
        return False, f"Rate limit exceeded. Try again later."
    
    cache.set(key, current_count + 1, window)
    return True, "Within rate limit"


def calculate_security_score(user, request_data=None):
    """Calculate user security score based on various factors"""
    score = 100  # Start with perfect score
    
    if not user.pgp_public_key:
        score -= 20
    
    from wallets.models import AuditLog
    recent_logs = AuditLog.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    )
    
    flagged_count = recent_logs.filter(flagged=True).count()
    if flagged_count > 0:
        score -= (flagged_count * 10)
    
    login_count = recent_logs.filter(action='login').count()
    if login_count > 20:  # Very frequent logins
        score -= 15
    
    return max(0, min(100, score))


def detect_suspicious_patterns(user, action, request_data=None):
    """Detect suspicious user behavior patterns"""
    risk_factors = []
    risk_score = 0
    
    from wallets.models import AuditLog
    recent_failures = AuditLog.objects.filter(
        user=user,
        action=action,
        details__success=False,
        created_at__gte=timezone.now() - timezone.timedelta(hours=1)
    ).count()
    
    if recent_failures > 3:
        risk_factors.append("Multiple recent failures")
        risk_score += 25
    
    recent_actions = AuditLog.objects.filter(
        user=user,
        action=action,
        created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).count()
    
    if recent_actions > 5:
        risk_factors.append("Rapid successive actions")
        risk_score += 20
    
    return {
        'risk_score': risk_score,
        'risk_factors': risk_factors,
        'requires_review': risk_score >= 40
    }


def clean_user_input(data):
    """Clean and sanitize user input"""
    if isinstance(data, str):
        cleaned = data.strip()
        cleaned = cleaned.replace('<', '&lt;').replace('>', '&gt;')
        return cleaned
    
    if isinstance(data, dict):
        return {key: clean_user_input(value) for key, value in data.items()}
    
    if isinstance(data, list):
        return [clean_user_input(item) for item in data]
    
    return data


def validate_withdrawal_security(user, amount, currency):
    """Validate withdrawal request security"""
    from wallets.models import WithdrawalRequest
    
    recent_withdrawals = WithdrawalRequest.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timezone.timedelta(hours=24)
    )
    
    total_recent = sum(wr.amount for wr in recent_withdrawals)
    
    risk_factors = []
    risk_score = 0
    
    if amount > getattr(settings, 'LARGE_WITHDRAWAL_THRESHOLD', 1.0):
        risk_factors.append("Large withdrawal amount")
        risk_score += 30
    
    if recent_withdrawals.count() > 3:
        risk_factors.append("Multiple recent withdrawals")
        risk_score += 25
    
    daily_limit = getattr(settings, 'DAILY_WITHDRAWAL_LIMIT', 5.0)
    if total_recent + amount > daily_limit:
        risk_factors.append("Exceeds daily limit")
        risk_score += 40
    
    return {
        'allowed': risk_score < 60,
        'risk_score': risk_score,
        'risk_factors': risk_factors,
        'requires_manual_review': risk_score >= 40
    }
