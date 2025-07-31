import environ
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)

import os
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", ".onion").split(",")
if ".onion" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".onion")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_ratelimit',
    'django_redis',
    'accounts',
    'wallets',
    'vendors',
    'products',
    'orders',
    'disputes',
    'messaging',
    'support',
    'adminpanel',
    'core',
    'apps.security',
    'apps.anti_ddos',
]

MIDDLEWARE = [
    'apps.anti_ddos.middleware.AntiDDoSMiddleware',
    
    'apps.security.openresty_middleware.OpenRestyIntegrationMiddleware',
    
    'apps.security.resource_protection.ResourceProtectionMiddleware',
    
    'apps.security.circuit_aware_defense.CircuitAwareDefense',
    
    'apps.security.fast_prefilter.FastPreFilterMiddleware',
    
    'apps.security.circuit_limiter.TorCircuitLimiter',
    
    'apps.security.optimized_middleware.OptimizedSecurityMiddleware',
    
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    'core.middleware.RateLimitMiddleware',
    'apps.security.middleware.CaptchaRateLimitMiddleware',
    'wallets.middleware.WalletSecurityMiddleware',
    'core.middleware.TorSecurityMiddleware',
]

ROOT_URLCONF = 'marketplace.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.security.context_processors.security_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'marketplace.wsgi.application'

DATABASES = {'default': env.db()}

DATABASES['default']['CONN_MAX_AGE'] = 600

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_ID = 1

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

ANTI_EVASION_CONFIG = {
    'OPENRESTY_INTEGRATION': {
        'ENABLE_DIRECT_ACCESS_BLOCKING': True,
        'REQUIRE_OPENRESTY_HEADERS': True,
        'POW_VERIFICATION_CACHE_TTL': 3600,
        'FINGERPRINT_TRACKING': True,
        'METRICS_COLLECTION': True,
    },
    
    'CIRCUIT_DEFENSE': {
        'THREAT_THRESHOLD_BLOCK': 70,      # Block at 70+ threat score
        'THREAT_THRESHOLD_PRESSURE': 50,   # Lower threshold under load
        'CIRCUIT_MEMORY_WINDOW': 600,      # 10-minute circuit memory
        'MAX_CIRCUIT_REQUESTS': 30,        # Max requests per circuit per 10 min
        'GLOBAL_RATE_THRESHOLD': 20,       # Block if >20 global RPS
        'MULTI_VECTOR_THRESHOLD': 3,       # Block if >3 attack vectors per circuit
    },
    
    'RESOURCE_PROTECTION': {
        'CRITICAL_CPU_THRESHOLD': 90,      # CPU% for critical load
        'HIGH_CPU_THRESHOLD': 75,          # CPU% for high load
        'CRITICAL_MEMORY_THRESHOLD': 95,   # Memory% for critical load
        'HIGH_MEMORY_THRESHOLD': 85,       # Memory% for high load
        'MAX_CONNECTIONS': 2000,           # Max concurrent connections
        'ADAPTIVE_TIMEOUT_MIN': 1000,      # Min timeout during attacks (1s)
        'ADAPTIVE_TIMEOUT_MAX': 5000,      # Max timeout during normal load (5s)
    },
    
    'ADAPTIVE_RATE_LIMITING': {
        'BASE_REQUESTS_PER_MINUTE': 20,
        'BASE_REQUESTS_PER_HOUR': 200,
        'BASE_BURST_LIMIT': 5,
        'ATTACK_REQUESTS_PER_MINUTE': 10,  # Reduced during attacks
        'ATTACK_REQUESTS_PER_HOUR': 100,   # Reduced during attacks
        'ATTACK_BURST_LIMIT': 3,           # Reduced during attacks
        'ADAPTATION_INTERVAL': 60,         # Adapt every minute
    },
}

SECURITY_MONITORING = {
    'ENABLE_METRICS': True,
    'METRICS_INTERVAL': 30,  # seconds
    'ALERT_THRESHOLDS': {
        'requests_per_second': 50,
        'block_rate_percent': 70,
        'response_time_ms': 500,
    }
}


RATELIMIT_CACHE_BACKEND = 'default'
RATELIMIT_ENABLE = True
RATELIMIT_VIEW = 'django.http.HttpResponseTooManyRequests'

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CELERY_BEAT_SCHEDULE = {
    'update-vendor-metrics': {
        'task': 'vendors.tasks.update_vendor_metrics',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-old-notifications': {
        'task': 'vendors.tasks.cleanup_old_notifications',
        'schedule': 86400.0,  # Daily
    },
    'refresh-tor-descriptors': {
        'task': 'vendors.tasks.refresh_tor_descriptors',
        'schedule': 43200.0,  # Every 12 hours
    },
    'reconcile-wallet-balances': {
        'task': 'wallets.tasks.reconcile_wallet_balances',
        'schedule': 21600.0,  # Every 6 hours
    },
    'cleanup-old-audit-logs': {
        'task': 'wallets.tasks.cleanup_old_audit_logs',
        'schedule': 86400.0,  # Daily
    },
    'check-suspicious-activity': {
        'task': 'wallets.tasks.check_suspicious_activity',
        'schedule': 1800.0,  # Every 30 minutes
    },
    'update-conversion-rates': {
        'task': 'wallets.tasks.update_conversion_rates',
        'schedule': 300.0,  # Every 5 minutes
    },
    'monitor-wallet-security': {
        'task': 'wallets.tasks.monitor_wallet_security',
        'schedule': 86400.0,  # Daily
    },
}

BTC_USD_RATE = 118905.27
XMR_USD_RATE = 340.67
BTC_EUR_RATE = 108000.00
XMR_EUR_RATE = 310.00
BITCOIND_RPC_URL = env('BITCOIND_RPC_URL', default="http://127.0.0.1:8332")
BITCOIND_RPC_USER = env('BITCOIND_RPC_USER')
BITCOIND_RPC_PASSWORD = env('BITCOIND_RPC_PASSWORD')
BITCOIN_TRANSACTION_SIGNALING = True
MONERO_WALLET_RPC_PORT = env.int('MONERO_WALLET_RPC_PORT', default=18088)
MONERO_DAEMON_RPC_PORT = env.int('MONERO_DAEMON_RPC_PORT', default=18081)
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

GPG_BINARY = '/usr/bin/gpg'

PGP_2FA_TIMEOUT = 15  # minutes
SESSION_SAVE_EVERY_REQUEST = False  # Don't refresh on every request for better 2FA experience
SESSION_COOKIE_SAMESITE = 'Lax'

CSRF_COOKIE_AGE = 3600  # 1 hour for CSRF tokens
CSRF_USE_SESSIONS = False  # Use cookie-based CSRF for better compatibility

IMAGE_UPLOAD_SETTINGS = {
    'MAX_FILE_SIZE': 2 * 1024 * 1024,  # 2MB max (reduced from 5MB)
    'ALLOWED_EXTENSIONS': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],  # Input formats
    'ALLOWED_MIMETYPES': [
        'image/jpeg', 
        'image/png', 
        'image/gif', 
        'image/bmp',
        'image/webp'
    ],
    
    'OUTPUT_FORMAT': 'JPEG',  # New setting
    'JPEG_QUALITY': 85,  # New setting
    'THUMBNAIL_QUALITY': 75,  # New setting
    'MAX_IMAGE_DIMENSIONS': (1920, 1080),  # Reduced from (2000, 2000)
    'THUMBNAIL_SIZE': (400, 400),
    'STRIP_METADATA': True,
    'REPROCESS_ALL': True,  # Always reprocess images for security
    
    'STORAGE_BACKEND': 'local',  # 'local' or 'remote'
    'LOCAL_UPLOAD_PATH': 'secure_uploads/',
    'REMOTE_STORAGE_CONFIG': {
        'HOST': os.environ.get('REMOTE_IMAGE_HOST', ''),
        'PORT': int(os.environ.get('REMOTE_IMAGE_PORT', 22)),
        'USERNAME': os.environ.get('REMOTE_IMAGE_USER', ''),
        'KEY_PATH': os.environ.get('REMOTE_IMAGE_KEY_PATH', ''),
        'REMOTE_PATH': os.environ.get('REMOTE_IMAGE_PATH', '/var/www/images/'),
        'PUBLIC_URL': os.environ.get('REMOTE_IMAGE_URL', ''),
    },
    
    'UPLOADS_PER_HOUR': 10,
    'UPLOADS_PER_DAY': 50,
}

SECURE_UPLOAD_ROOT = BASE_DIR / 'secure_uploads'
SECURE_UPLOAD_ROOT.mkdir(exist_ok=True)

TEMP_UPLOAD_ROOT = BASE_DIR / 'temp_uploads'
TEMP_UPLOAD_ROOT.mkdir(exist_ok=True)

WALLET_SECURITY = {
    'WITHDRAWAL_RATE_LIMIT': 5,  # Max withdrawal attempts per hour
    'CONVERSION_RATE_LIMIT': 20,  # Max conversions per hour
    'LOGIN_RATE_LIMIT': 10,  # Max login attempts per hour
    
    'DEFAULT_DAILY_WITHDRAWAL_LIMIT_BTC': '1.0',
    'DEFAULT_DAILY_WITHDRAWAL_LIMIT_XMR': '100.0',
    
    'RISK_SCORE_LOW': 20,
    'RISK_SCORE_MEDIUM': 40,
    'RISK_SCORE_HIGH': 60,
    'RISK_SCORE_MANUAL_REVIEW': 40,
    
    'REQUIRE_IP_MATCH': False,  # Disabled for Tor compatibility
    'SESSION_TIMEOUT_MINUTES': 30,  # Auto logout after inactivity
    
    '2FA_VALIDITY_WINDOW': 1,  # TOTP window (30 second intervals)
    '2FA_ISSUER_NAME': 'Secure Marketplace',
    
    'AUDIT_LOG_RETENTION_DAYS': 365,
    
    'RECONCILIATION_SCHEDULE': '0 */6 * * *',  # Every 6 hours
}

SECURITY_SETTINGS = {
    'ENABLE_BOT_DETECTION': True,
    'ENABLE_RATE_LIMITING': True,
    'ENABLE_HONEYPOT_PROTECTION': True,
    'ENABLE_MATH_CAPTCHA': True,
    'MAX_LOGIN_ATTEMPTS_PER_IP': 20,
    'MAX_LOGIN_ATTEMPTS_PER_USER': 5,
    'MAX_REGISTRATION_ATTEMPTS_PER_IP': 3,
    'FORM_SUBMISSION_RATE_LIMIT': 10,
    'SESSION_SECURITY_TIMEOUT': 3600,
}

ADMIN_EMAIL = env('ADMIN_EMAIL', default='admin@marketplace.local')

ADMIN_SECURITY = {
    'REQUIRE_TRIPLE_AUTH': True,
    'SECONDARY_PASSWORD': 'admin_secure_2024!',
    'PGP_REQUIRED': True,
    'SESSION_TIMEOUT_MINUTES': 30,
    'MAX_FAILED_ATTEMPTS': 3,
    'LOCKOUT_DURATION_MINUTES': 15,
    'CHALLENGE_TIMEOUT_MINUTES': 5,
    'LOG_ALL_ACTIONS': True,
    'REQUIRE_IP_CONSISTENCY': True,
}

try:
    from config.admin_config import ADMIN_PANEL_CONFIG, ADMIN_PGP_CONFIG
except ImportError:
    ADMIN_PANEL_CONFIG = {
        'SECONDARY_PASSWORD': 'admin_secure_2024!',
        'REQUIRE_PGP_AFTER_AUTH': True,
        'MAX_FAILED_ATTEMPTS': 3,
        'LOCKOUT_DURATION': 900,  # 15 minutes
        'SESSION_TIMEOUT': 1800,  # 30 minutes
    }
    ADMIN_PGP_CONFIG = {
        'ENFORCE_PGP': True,
        'CHALLENGE_TIMEOUT': 300,  # 5 minutes
        'ADMIN_PUBLIC_KEY': '''-----BEGIN PGP PUBLIC KEY BLOCK-----
-----END PGP PUBLIC KEY BLOCK-----''',
    }

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

CIRCUIT_FINGERPRINT_SECRET = b'super-secret-key-for-circuit-fingerprinting-change-in-production'

FAST_PREFILTER_RATE_LIMIT = {
    'per_minute': 50,  # 50 requests per minute for public IPs
    'burst': 20,       # Allow burst of 20 additional requests
}
