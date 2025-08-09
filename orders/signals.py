from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Order


def _bump(domain):
    key = f"version:{domain}"
    try:
        cache.incr(key)
    except Exception:
        val = cache.get(key)
        try:
            val_int = int(val) if val is not None else 1
        except Exception:
            val_int = 1
        cache.set(key, val_int + 1, None)


@receiver(post_save, sender=Order)
def order_saved(sender, **kwargs):
    _bump("order")


@receiver(post_delete, sender=Order)
def order_deleted(sender, **kwargs):
    _bump("order")
