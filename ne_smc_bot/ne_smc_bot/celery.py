import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ne_smc_bot.settings.dev')

app = Celery('ne_smc_bot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()