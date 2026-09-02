"""
apps/notifications/services/email_service.py

Envoi d'emails via le backend Django configuré (console en dev,
SMTP en production via EMAIL_BACKEND dans .env/settings.py).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("apps.notifications")


class EmailService:
    def send(self, to_email: str, subject: str, message: str) -> tuple[bool, str]:
        if not to_email:
            return False, "Adresse email manquante"
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            return True, ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Échec envoi email à %s : %s", to_email, exc)
            return False, str(exc)
