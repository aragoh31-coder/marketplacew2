from django.core.cache import cache as django_cache


def log_event(event_type, data):
    """Log security and audit events"""
    pass


cache = django_cache
