import os
import logging
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

app = Celery('marketplace')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks(['vendors', 'accounts', 'orders', 'products'])

logger = logging.getLogger(__name__)

@app.task(bind=True)
def debug_task(self):
    logger.debug(f'Request: {self.request!r}')
