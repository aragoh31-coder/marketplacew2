from django import template
from django.core.cache import cache

register = template.Library()


@register.simple_tag
def cache_version(domain):
    key = f"version:{domain}"
    val = cache.get(key)
    try:
        return int(val) if val is not None else 1
    except (TypeError, ValueError):
        return 1
