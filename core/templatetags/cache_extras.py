from django import template
from django.core.cache import cache
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

register = template.Library()

@register.simple_tag
def cache_version(domain):
    key = f"version:{domain}"
    val = cache.get(key)
    try:
        return int(val) if val is not None else 1
    except (TypeError, ValueError):
        return 1

@register.filter(name="normalize_qs")
def normalize_qs(path_or_url):
    if not isinstance(path_or_url, str) or not path_or_url:
        return ""
    parts = urlsplit(path_or_url)
    query = parts.query or ""
    if not query:
        return parts.path or "/"
    skip_keys = {"sessionid", "csrftoken"}
    params = [
        (k, v) for (k, v) in parse_qsl(query, keep_blank_values=False)
        if k not in skip_keys and not k.startswith("utm_") and not k.startswith("_")
    ]
    if not params:
        return parts.path or "/"
    params.sort(key=lambda kv: (kv[0], kv[1]))
    norm_q = urlencode(params, doseq=True)
    return urlunsplit(("", "", parts.path or "/", norm_q, ""))
