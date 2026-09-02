# S'assure que l'app Celery est chargée dès le démarrage de Django,
# pour que @shared_task fonctionne partout dans le projet.
from .celery import app as celery_app

__all__ = ("celery_app",)
