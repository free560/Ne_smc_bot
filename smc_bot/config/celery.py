"""
config/celery.py

Configuration Celery pour le scanner temps réel (Phase future : exécution
périodique du scan sur BOOM1000/CRASH1000). Le broker/backend Redis est
défini via .env (CELERY_BROKER_URL / CELERY_RESULT_BACKEND).
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("smc_bot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Planification par défaut : scan de tous les instruments toutes les minutes
# sur M1 (le RSI de timing) ; ajuster selon la charge réelle une fois les
# credentials Deriv en place. Décommenter pour activer le battement Celery.
app.conf.beat_schedule = {
    # "scan-every-minute": {
    #     "task": "apps.scanner.tasks.scan_all_instruments",
    #     "schedule": crontab(minute="*"),
    # },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Requête : {self.request!r}")
