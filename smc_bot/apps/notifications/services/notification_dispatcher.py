"""
apps/notifications/services/notification_dispatcher.py

Point d'entrée unique pour émettre une notification : quel que soit
l'événement (nouveau signal, alerte risque, drawdown, pertes
consécutives, marché en range), le dispatcher :
  1. Journalise toujours l'événement (canal DASHBOARD, visible dans
     le module Notifications, même si aucun canal externe n'est configuré)
  2. Envoie sur Telegram si l'utilisateur l'a activé et a un chat_id
  3. Envoie par email si l'utilisateur l'a activé

Chaque tentative (succès ou échec) est journalisée dans NotificationLog.
"""

from __future__ import annotations

from apps.notifications.models import Channel, EventType, NotificationLog, NotificationPreference
from apps.notifications.services.email_service import EmailService
from apps.notifications.services.telegram_service import TelegramService


class NotificationDispatcher:
    def __init__(self, telegram_service: TelegramService | None = None, email_service: EmailService | None = None):
        self.telegram_service = telegram_service or TelegramService()
        self.email_service = email_service or EmailService()

    def dispatch(self, event_type: str, message: str, user=None) -> list[NotificationLog]:
        logs = [self._log_dashboard(event_type, message, user)]

        if user is None:
            return logs

        preference = NotificationPreference.objects.filter(user=user).first()
        if preference is None:
            return logs

        if not self._event_enabled(event_type, preference):
            return logs

        if preference.telegram_enabled:
            chat_id = getattr(getattr(user, "profile", None), "telegram_chat_id", "")
            success, error = self.telegram_service.send(chat_id, message)
            logs.append(self._log(event_type, Channel.TELEGRAM, message, user, success, error))

        if preference.email_enabled:
            success, error = self.email_service.send(preference.resolved_email, f"[SMC BOT] {event_type}", message)
            logs.append(self._log(event_type, Channel.EMAIL, message, user, success, error))

        return logs

    # ------------------------------------------------------------------
    @staticmethod
    def _event_enabled(event_type: str, preference: NotificationPreference) -> bool:
        if event_type == EventType.RANGE_MARKET_ALERT:
            return preference.notify_on_range_market
        if event_type == EventType.NEW_SIGNAL:
            return preference.notify_on_signal
        return preference.notify_on_risk_alert  # RISK_ALERT / DRAWDOWN_ALERT / CONSECUTIVE_LOSS_ALERT

    @staticmethod
    def _log_dashboard(event_type: str, message: str, user) -> NotificationLog:
        return NotificationLog.objects.create(
            user=user, event_type=event_type, channel=Channel.DASHBOARD, message=message, success=True,
        )

    @staticmethod
    def _log(event_type: str, channel: str, message: str, user, success: bool, error: str) -> NotificationLog:
        return NotificationLog.objects.create(
            user=user, event_type=event_type, channel=channel, message=message,
            success=success, error_message=error,
        )
