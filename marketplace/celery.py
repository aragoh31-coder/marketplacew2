import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marketplace.settings")

app = Celery("marketplace")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(["vendors", "accounts", "orders", "products"])

from celery.schedules import crontab

app.conf.beat_schedule = {
    "recalculate-vendor-trust-levels": {
        "task": "vendors.tasks.recalculate_vendor_trust_levels",
        "schedule": crontab(hour=2, minute=0),
    },
    "update-stale-trust-scores": {
        "task": "vendors.tasks.update_stale_trust_scores",
        "schedule": crontab(hour="*/6", minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
