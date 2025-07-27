import logging
from django.utils.timezone import now

logger = logging.getLogger('audit')

def log_admin_action(admin_user, action):
    """Log admin actions for comprehensive audit trail"""
    log_entry = f"[{now()}] ADMIN: {admin_user.username} ACTION: {action}"
    logger.info(log_entry)
    
    try:
        from adminpanel.models import AdminLog
        AdminLog.objects.create(
            admin_user=admin_user,
            action_type='SECURITY',
            target_model='WithdrawalRequest',
            description=action,
            timestamp=now()
        )
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
