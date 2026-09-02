"""
apps/notifications/services/telegram_service.py

Envoi de messages via l'API Bot Telegram (https://core.telegram.org/bots/api).
Ne lève jamais d'exception vers l'appelant : renvoie un booléen de succès,
l'erreur détaillée étant journalisée par le NotificationDispatcher.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("apps.notifications")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT_SECONDS = 10


class TelegramService:
    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN

    def send(self, chat_id: str, text: str) -> tuple[bool, str]:
        """Renvoie (succès, message_erreur_ou_vide)."""
        if not self.bot_token:
            return False, "TELEGRAM_BOT_TOKEN non configuré"
        if not chat_id:
            return False, "chat_id manquant"

        url = TELEGRAM_API_BASE.format(token=self.bot_token)
        try:
            response = requests.post(
                url, json={"chat_id": chat_id, "text": text}, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok", False):
                error = payload.get("description", "Erreur Telegram inconnue")
                logger.warning("Échec envoi Telegram : %s", error)
                return False, error
            return True, ""
        except requests.RequestException as exc:
            logger.warning("Échec envoi Telegram (réseau) : %s", exc)
            return False, str(exc)
