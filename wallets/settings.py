WALLET_SECURITY = {
    'WITHDRAWAL_RATE_LIMIT': 5,
    'CONVERSION_RATE_LIMIT': 20,
    'LOGIN_RATE_LIMIT': 10,
    
    'DEFAULT_DAILY_WITHDRAWAL_LIMIT_BTC': '1.0',
    'DEFAULT_DAILY_WITHDRAWAL_LIMIT_XMR': '100.0',
    
    'RISK_SCORE_LOW': 20,
    'RISK_SCORE_MEDIUM': 40,
    'RISK_SCORE_HIGH': 60,
    'RISK_SCORE_MANUAL_REVIEW': 40,
    
    'SESSION_TIMEOUT_MINUTES': 30,
    
    '2FA_VALIDITY_WINDOW': 1,
    '2FA_ISSUER_NAME': 'Secure Marketplace',
    
    'AUDIT_LOG_RETENTION_DAYS': 365,
    
    'RECONCILIATION_SCHEDULE': '0 */6 * * *',
}

WALLET_SESSION_TIMEOUT_MINUTES = 30

WALLET_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'wallet_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/wallet.log',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'wallet_security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/wallet_security.log',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'wallet': {
            'handlers': ['wallet_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'wallet.security': {
            'handlers': ['wallet_security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'wallet.admin': {
            'handlers': ['wallet_security_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
