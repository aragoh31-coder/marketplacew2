import json
import logging

from django.conf import settings
from django.utils import timezone


class AuditLogger:
    """Centralized audit logging system"""

    def __init__(self):
        self.logger = logging.getLogger("marketplace.audit")

    def log_user_action(
        self, user, action, details=None, request=None, risk_level="low"
    ):
        """Log user actions with context"""
        try:
            log_data = {
                "timestamp": timezone.now().isoformat(),
                "user_id": str(user.id) if user else None,
                "username": user.username if user else "anonymous",
                "action": action,
                "risk_level": risk_level,
                "details": details or {},
            }

            if request:
                log_data.update(
                    {
                        "request_id": getattr(request, "log_id", "unknown"),
                        "path": request.path,
                        "method": request.method,
                        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                    }
                )

            self.logger.info(f"User action: {action}", extra=log_data)

        except Exception as e:
            logging.error(f"Failed to log user action: {e}")

    def log_security_event(
        self, event_type, risk_level, details=None, user=None, request=None
    ):
        """Log security events"""
        try:
            log_data = {
                "timestamp": timezone.now().isoformat(),
                "event_type": event_type,
                "risk_level": risk_level,
                "details": details or {},
            }

            if user:
                log_data.update(
                    {
                        "user_id": str(user.id),
                        "username": user.username,
                    }
                )

            if request:
                log_data.update(
                    {
                        "request_id": getattr(request, "log_id", "unknown"),
                        "path": request.path,
                        "method": request.method,
                    }
                )

            logger = logging.getLogger("marketplace.security")
            logger.warning(f"Security event: {event_type}", extra=log_data)

        except Exception as e:
            logging.error(f"Failed to log security event: {e}")

    def log_transaction(
        self, transaction_type, amount, currency, user=None, details=None
    ):
        """Log financial transactions"""
        try:
            log_data = {
                "timestamp": timezone.now().isoformat(),
                "transaction_type": transaction_type,
                "amount": str(amount),
                "currency": currency,
                "details": details or {},
            }

            if user:
                log_data.update(
                    {
                        "user_id": str(user.id),
                        "username": user.username,
                    }
                )

            logger = logging.getLogger("marketplace.transactions")
            logger.info(f"Transaction: {transaction_type}", extra=log_data)

        except Exception as e:
            logging.error(f"Failed to log transaction: {e}")

    def log_admin_action(
        self, admin_user, action, target=None, details=None, request=None
    ):
        """Log administrative actions"""
        try:
            log_data = {
                "timestamp": timezone.now().isoformat(),
                "admin_user_id": str(admin_user.id),
                "admin_username": admin_user.username,
                "action": action,
                "details": details or {},
            }

            if target:
                log_data["target"] = str(target)

            if request:
                log_data.update(
                    {
                        "request_id": getattr(request, "log_id", "unknown"),
                        "path": request.path,
                        "method": request.method,
                    }
                )

            logger = logging.getLogger("marketplace.audit")
            logger.info(f"Admin action: {action}", extra=log_data)

        except Exception as e:
            logging.error(f"Failed to log admin action: {e}")


audit_logger = AuditLogger()
