from django.core.cache import cache as django_cache


def log_event(event_type, data):
    """Log security and audit events"""
    import logging
    import json
    from datetime import datetime
    from django.conf import settings
    
    logger = logging.getLogger('security.audit')
    
    # Format event data
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'type': event_type,
        'data': data
    }
    
    # Log to security audit log
    logger.info(json.dumps(event))
    
    # Also cache recent events for monitoring
    cache_key = f'security_event:{event_type}:{datetime.utcnow().strftime("%Y%m%d%H")}'
    cached_events = django_cache.get(cache_key, [])
    cached_events.append(event)
    
    # Keep only last 100 events per hour
    if len(cached_events) > 100:
        cached_events = cached_events[-100:]
    
    # Cache for 1 hour
    django_cache.set(cache_key, cached_events, 3600)


cache = django_cache
