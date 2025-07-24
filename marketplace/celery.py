import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')

app = Celery('marketplace')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks(['vendors', 'accounts', 'orders', 'products'])

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
