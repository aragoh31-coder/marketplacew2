import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")

REQUEST_SIG_SECRET = env("REQUEST_SIG_SECRET", default=SECRET_KEY)

DEBUG = env.bool("DEBUG", default=False)

import os

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", ".onion").split(",")
if ".onion" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onion")
for host in ["localhost", "127.0.0.1", "django", "openresty"]:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)
ONION_HOST = os.getenv("ONION_HOST", "").strip()
if ONION_HOST and ONION_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(ONION_HOST)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django_ratelimit",
    "django_redis",
    "accounts",
    "wallets",
    "vendors",
    "products",
    "orders",
    "disputes",
    "messaging",
    "support",
    "adminpanel",
    "core",
    "apps.security",
    "apps.anti_ddos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.anti_ddos.middleware.AntiDDoSMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.security.TorSecurityMiddleware",
    "apps.security.middleware.TwoFactorAuthMiddleware",
    "apps.security.middleware.TorSecurityHeadersMiddleware",
]

ROOT_URLCONF = "marketplace.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.security.context_processors.security_context",
                "apps.security.context_processors.captcha_data",
                "core.context_processors.marketplace_context",
            ],
        },
    },
]

WSGI_APPLICATION = "marketplace.wsgi.application"

DATABASES = {"default": env.db()}

DATABASES["default"]["CONN_MAX_AGE"] = 600

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

ANTI_EVASION_CONFIG = {
    "OPENRESTY_INTEGRATION": {
        "ENABLE_DIRECT_ACCESS_BLOCKING": True,
        "REQUIRE_OPENRESTY_HEADERS": True,
        "POW_VERIFICATION_CACHE_TTL": 3600,
        "FINGERPRINT_TRACKING": True,
        "METRICS_COLLECTION": True,
    },
    "CIRCUIT_DEFENSE": {
        "THREAT_THRESHOLD_BLOCK": 70,  # Block at 70+ threat score
        "THREAT_THRESHOLD_PRESSURE": 50,  # Lower threshold under load
        "CIRCUIT_MEMORY_WINDOW": 600,  # 10-minute circuit memory
        "MAX_CIRCUIT_REQUESTS": 30,  # Max requests per circuit per 10 min
        "GLOBAL_RATE_THRESHOLD": 20,  # Block if >20 global RPS
        "MULTI_VECTOR_THRESHOLD": 3,  # Block if >3 attack vectors per circuit
    },
    "RESOURCE_PROTECTION": {
        "CRITICAL_CPU_THRESHOLD": 90,  # CPU% for critical load
        "HIGH_CPU_THRESHOLD": 75,  # CPU% for high load
        "CRITICAL_MEMORY_THRESHOLD": 95,  # Memory% for critical load
        "HIGH_MEMORY_THRESHOLD": 85,  # Memory% for high load
        "MAX_CONNECTIONS": 2000,  # Max concurrent connections
        "ADAPTIVE_TIMEOUT_MIN": 1000,  # Min timeout during attacks (1s)
        "ADAPTIVE_TIMEOUT_MAX": 5000,  # Max timeout during normal load (5s)
    },
    "ADAPTIVE_RATE_LIMITING": {
        "BASE_REQUESTS_PER_MINUTE": 20,
        "BASE_REQUESTS_PER_HOUR": 200,
        "BASE_BURST_LIMIT": 5,
        "ATTACK_REQUESTS_PER_MINUTE": 10,  # Reduced during attacks
        "ATTACK_REQUESTS_PER_HOUR": 100,  # Reduced during attacks
        "ATTACK_BURST_LIMIT": 3,  # Reduced during attacks
        "ADAPTATION_INTERVAL": 60,  # Adapt every minute
    },
}

SECURITY_MONITORING = {
    "ENABLE_METRICS": True,
    "METRICS_INTERVAL": 30,  # seconds
    "ALERT_THRESHOLDS": {
        "requests_per_second": 50,
        "block_rate_percent": 70,
        "response_time_ms": 500,
    },
}


RATELIMIT_CACHE_BACKEND = "default"
RATELIMIT_ENABLE = True
RATELIMIT_VIEW = "django.http.HttpResponseTooManyRequests"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "no-referrer"
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False
SECURE_PROXY_SSL_HEADER = None
SESSION_COOKIE_SECURE = not env.bool("ALLOW_INSECURE_ONION_COOKIES", default=False)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = not env.bool("ALLOW_INSECURE_ONION_COOKIES", default=False)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
ANTIDDOS = dict(
    TTL=900,
    POW_PREFIX="0000",
    AUTO_POW=True,
    AUTO_POW_TIMEOUT=8,
    AUTO_POW_MAX_REFRESH=6,
)


CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CELERY_BEAT_SCHEDULE = {
    "update-vendor-metrics": {
        "task": "vendors.tasks.update_vendor_metrics",
        "schedule": 3600.0,  # Every hour
    },
    "cleanup-old-notifications": {
        "task": "vendors.tasks.cleanup_old_notifications",
        "schedule": 86400.0,  # Daily
    },
    "refresh-tor-descriptors": {
        "task": "vendors.tasks.refresh_tor_descriptors",
        "schedule": 43200.0,  # Every 12 hours
    },
    "reconcile-wallet-balances": {
        "task": "wallets.tasks.reconcile_wallet_balances",
        "schedule": 21600.0,  # Every 6 hours
    },
    "cleanup-old-audit-logs": {
        "task": "wallets.tasks.cleanup_old_audit_logs",
        "schedule": 86400.0,  # Daily
    },
    "check-suspicious-activity": {
        "task": "wallets.tasks.check_suspicious_activity",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "update-conversion-rates": {
        "task": "wallets.tasks.update_conversion_rates",
        "schedule": 300.0,  # Every 5 minutes
    },
    "monitor-wallet-security": {
        "task": "wallets.tasks.monitor_wallet_security",
        "schedule": 86400.0,  # Daily
    },
}

BTC_USD_RATE = 118905.27
XMR_USD_RATE = 340.67
BTC_EUR_RATE = 108000.00
XMR_EUR_RATE = 310.00
BITCOIND_RPC_URL = env("BITCOIND_RPC_URL", default="http://127.0.0.1:8332")
BITCOIND_RPC_USER = env("BITCOIND_RPC_USER")
BITCOIND_RPC_PASSWORD = env("BITCOIND_RPC_PASSWORD")
BITCOIN_TRANSACTION_SIGNALING = True
MONERO_WALLET_RPC_PORT = env.int("MONERO_WALLET_RPC_PORT", default=18088)
MONERO_DAEMON_RPC_PORT = env.int("MONERO_DAEMON_RPC_PORT", default=18081)
BTC_REQUIRED_CONFIRMATIONS = 1
XMR_REQUIRED_CONFIRMATIONS = 10

from core.logging.config import get_logging_config

LOGGING = get_logging_config()

# LOGGING['handlers'].update({
#     'security_file': {
#         'level': 'INFO',
#         'class': 'logging.handlers.RotatingFileHandler',
#         'filename': '/app/logs/security_advanced.log',
#         'maxBytes': 50*1024*1024,  # 50MB
#         'backupCount': 5,
#         'formatter': 'detailed',
#     },
#     'attack_analysis': {
#         'level': 'WARNING',
#         'class': 'logging.handlers.RotatingFileHandler',
#         'filename': '/app/logs/attack_analysis.log',
#         'maxBytes': 100*1024*1024,  # 100MB
#         'backupCount': 10,
#         'formatter': 'detailed',
#     },
#     'performance': {
#         'level': 'INFO',
#         'class': 'logging.handlers.RotatingFileHandler',
#         'filename': '/app/logs/performance.log',
#         'maxBytes': 25*1024*1024,  # 25MB
#         'backupCount': 3,
#         'formatter': 'detailed',
#     }
# })

# LOGGING['loggers'].update({
#     'security': {
#         'handlers': ['security_file', 'attack_analysis'],
#         'level': 'INFO',
#         'propagate': False,
#     },
#     'performance': {
#         'handlers': ['performance'],
#         'level': 'INFO',
#         'propagate': False,
#     }
# })


POW_DIFFICULTY = 4  # Number of leading zeros required

GPG_BINARY = "/usr/bin/gpg"

PGP_2FA_TIMEOUT = 15  # minutes
SESSION_SAVE_EVERY_REQUEST = (
    False  # Don't refresh on every request for better 2FA experience
)
SESSION_COOKIE_AGE = 900  # 15 minutes for Tor security
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Don't use cookies for session data

CSRF_COOKIE_AGE = 3600  # 1 hour for CSRF tokens
CSRF_USE_SESSIONS = False  # Use cookie-based CSRF for better compatibility
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000', 'http://django:8000']
if ONION_HOST:
    CSRF_TRUSTED_ORIGINS.extend([f"http://{ONION_HOST}", f"https://{ONION_HOST}"])
CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'

IMAGE_UPLOAD_SETTINGS = {
    "MAX_FILE_SIZE": 2 * 1024 * 1024,  # 2MB max (reduced from 5MB)
    "ALLOWED_EXTENSIONS": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],  # Input formats
    "ALLOWED_MIMETYPES": [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/webp",
    ],
    "OUTPUT_FORMAT": "JPEG",  # New setting
    "JPEG_QUALITY": 85,  # New setting
    "THUMBNAIL_QUALITY": 75,  # New setting
    "MAX_IMAGE_DIMENSIONS": (1920, 1080),  # Reduced from (2000, 2000)
    "THUMBNAIL_SIZE": (400, 400),
    "STRIP_METADATA": True,
    "REPROCESS_ALL": True,  # Always reprocess images for security
    "STORAGE_BACKEND": "local",  # 'local' or 'remote'
    "LOCAL_UPLOAD_PATH": "secure_uploads/",
    "REMOTE_STORAGE_CONFIG": {
        "HOST": os.environ.get("REMOTE_IMAGE_HOST", ""),
        "PORT": int(os.environ.get("REMOTE_IMAGE_PORT", 22)),
        "USERNAME": os.environ.get("REMOTE_IMAGE_USER", ""),
        "KEY_PATH": os.environ.get("REMOTE_IMAGE_KEY_PATH", ""),
        "REMOTE_PATH": os.environ.get("REMOTE_IMAGE_PATH", "/var/www/images/"),
        "PUBLIC_URL": os.environ.get("REMOTE_IMAGE_URL", ""),
    },
    "UPLOADS_PER_HOUR": 10,
    "UPLOADS_PER_DAY": 50,
}

SECURE_UPLOAD_ROOT = BASE_DIR / "secure_uploads"
SECURE_UPLOAD_ROOT.mkdir(exist_ok=True)

TEMP_UPLOAD_ROOT = BASE_DIR / "temp_uploads"
TEMP_UPLOAD_ROOT.mkdir(exist_ok=True)

SECURITY_CONFIG = {
    "RATE_LIMITS": {
        "requests_per_minute": 50,
        "requests_per_hour": 500,
        "burst_limit": 20,
        "withdrawal_rate_limit": 5,
        "conversion_rate_limit": 20,
        "login_rate_limit": 10,
        "max_login_attempts_per_ip": 20,
        "max_login_attempts_per_user": 5,
        "max_registration_attempts_per_ip": 3,
        "form_submission_rate_limit": 10,
    },
    "BOT_DETECTION": {
        "enable_bot_detection": True,
        "enable_honeypot_protection": True,
        "enable_math_captcha": True,
    },
    "WALLET_SECURITY": {
        "default_daily_withdrawal_limit_btc": "1.0",
        "default_daily_withdrawal_limit_xmr": "100.0",
        "risk_score_low": 20,
        "risk_score_medium": 40,
        "risk_score_high": 60,
        "risk_score_manual_review": 40,
        "require_ip_match": False,
        "session_timeout_minutes": 30,
        "2fa_validity_window": 1,
        "2fa_issuer_name": "Secure Marketplace",
        "audit_log_retention_days": 365,
        "reconciliation_schedule": "0 */6 * * *",
    },
    "ADMIN_SECURITY": {
        "require_triple_auth": True,
        "secondary_password": env("ADMIN_SECONDARY_PASSWORD", default=""),
        "pgp_required": True,
        "session_timeout_minutes": 30,
        "max_failed_attempts": 3,
        "lockout_duration_minutes": 15,
        "challenge_timeout_minutes": 5,
        "log_all_actions": True,
        "require_ip_consistency": True,
    },
    "SESSION_SECURITY": {
        "session_security_timeout": 3600,
    },
}

ADMIN_EMAIL = env("ADMIN_EMAIL", default="admin@marketplace.local")

try:
    from config.admin_config import ADMIN_PANEL_CONFIG, ADMIN_PGP_CONFIG
except ImportError:
    ADMIN_PANEL_CONFIG = {
        "SECONDARY_PASSWORD": env("ADMIN_SECONDARY_PASSWORD", default=""),
        "REQUIRE_PGP_AFTER_AUTH": True,
        "MAX_FAILED_ATTEMPTS": 3,
        "LOCKOUT_DURATION": 900,  # 15 minutes
        "SESSION_TIMEOUT": 1800,  # 30 minutes
    }
    ADMIN_PGP_CONFIG = {
        "ENFORCE_PGP": True,
        "CHALLENGE_TIMEOUT": 300,  # 5 minutes
        "ADMIN_PUBLIC_KEY": """-----BEGIN PGP PUBLIC KEY BLOCK-----
-----END PGP PUBLIC KEY BLOCK-----""",
    }

CSRF_COOKIE_SECURE = not env.bool("ALLOW_INSECURE_ONION_COOKIES", default=False)
SESSION_COOKIE_SECURE = not env.bool("ALLOW_INSECURE_ONION_COOKIES", default=False)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# try:
#     from .settings.local import *
# except ImportError:
#     pass


CIRCUIT_FINGERPRINT_SECRET = env("CIRCUIT_FINGERPRINT_SECRET").encode()

FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")

TOTP_ENCRYPTION_KEY = env("TOTP_ENCRYPTION_KEY")

TWO_FACTOR_AUTH = {
    "TOTP_ISSUER_NAME": "Tor Marketplace",
    "TOTP_WINDOW": 1,
    "BACKUP_CODE_COUNT": 10,
    "ENFORCE_2FA_FOR_ADMIN": True,
    "ENFORCE_2FA_FOR_WITHDRAWALS": True,
    "WITHDRAWAL_2FA_THRESHOLD_USD": 100,
    "QR_CODE_VERSION": 1,
    "RATE_LIMIT_ATTEMPTS": 5,
    "RATE_LIMIT_WINDOW": 300,
}

WALLET_SECURITY = {
    "REQUIRE_2FA_ABOVE_USD": 100,
    "MAX_DAILY_WITHDRAWAL_USD": 10000,
    "SUSPICIOUS_ACTIVITY_THRESHOLD": 5,
    "AUTO_LOCK_AFTER_FAILED_ATTEMPTS": 5,
    "SESSION_TIMEOUT_MINUTES": 30,
}

ADMIN_SECURITY = {
    "REQUIRE_TRIPLE_AUTH": True,
    "SECONDARY_PASSWORD_REQUIRED": True,
    "PGP_CHALLENGE_REQUIRED": True,
    "SESSION_TIMEOUT_MINUTES": 15,
    "MAX_LOGIN_ATTEMPTS": 3,
    "LOCKOUT_DURATION_MINUTES": 30,
}

BOT_DETECTION = {
    "ENABLE_FINGERPRINTING": True,
    "SUSPICIOUS_PATTERNS": [
        "rapid_requests",
        "automated_behavior",
        "unusual_user_agent",
    ],
    "RATE_LIMIT_THRESHOLD": 100,
    "CAPTCHA_THRESHOLD": 10,
}

RATE_LIMITING = {
    "LOGIN_ATTEMPTS": "5/5m",
    "REGISTRATION_ATTEMPTS": "3/10m",
    "PASSWORD_RESET_ATTEMPTS": "3/15m",
    "WITHDRAWAL_REQUESTS": "5/1h",
    "API_REQUESTS": "100/1h",
}
