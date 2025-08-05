import logging
import os

from django.conf import settings
from django.utils import timezone


class MarketplaceLogFormatter(logging.Formatter):
    """Custom log formatter for marketplace"""

    def format(self, record):
        record.timestamp = timezone.now().isoformat()

        if hasattr(record, "user_id"):
            record.user_info = f"[User:{record.user_id}]"
        else:
            record.user_info = "[Anonymous]"

        if hasattr(record, "request_id"):
            record.request_info = f"[Req:{record.request_id}]"
        else:
            record.request_info = ""

        return super().format(record)


def get_logging_config():
    """Get comprehensive logging configuration"""

    log_dir = os.path.join(settings.BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "()": "core.logging.config.MarketplaceLogFormatter",
                "format": "{timestamp} {levelname} {user_info} {request_info} {name}: {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {name}: {message}",
                "style": "{",
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(timestamp)s %(levelname)s %(name)s %(user_id)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "level": "INFO",
            },
            "file_general": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "marketplace.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter": "verbose",
                "level": "INFO",
            },
            "file_security": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "security.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 10,
                "formatter": "verbose",
                "level": "WARNING",
            },
            "file_audit": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "audit.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 20,
                "formatter": "json",
                "level": "INFO",
            },
            "file_errors": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "errors.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 10,
                "formatter": "verbose",
                "level": "ERROR",
            },
            "file_transactions": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "transactions.log"),
                "maxBytes": 50 * 1024 * 1024,  # 50MB
                "backupCount": 30,
                "formatter": "json",
                "level": "INFO",
            },
        },
        "loggers": {
            "django": {
                "handlers": ["console", "file_general"],
                "level": "INFO",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["file_security", "console"],
                "level": "WARNING",
                "propagate": False,
            },
            "marketplace.security": {
                "handlers": ["file_security", "file_audit"],
                "level": "INFO",
                "propagate": False,
            },
            "marketplace.audit": {
                "handlers": ["file_audit"],
                "level": "INFO",
                "propagate": False,
            },
            "marketplace.transactions": {
                "handlers": ["file_transactions", "file_audit"],
                "level": "INFO",
                "propagate": False,
            },
            "marketplace.errors": {
                "handlers": ["file_errors", "console"],
                "level": "ERROR",
                "propagate": False,
            },
            "wallets": {
                "handlers": ["file_transactions", "file_audit", "console"],
                "level": "INFO",
                "propagate": False,
            },
            "orders": {
                "handlers": ["file_audit", "file_general"],
                "level": "INFO",
                "propagate": False,
            },
            "vendors": {
                "handlers": ["file_audit", "file_general"],
                "level": "INFO",
                "propagate": False,
            },
            "accounts": {
                "handlers": ["file_security", "file_audit"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console", "file_general", "file_errors"],
            "level": "INFO",
        },
    }


class RequestLoggingMiddleware:
    """Middleware to add request context to logs"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import uuid

        request.log_id = str(uuid.uuid4())[:8]

        response = self.get_response(request)
        return response
