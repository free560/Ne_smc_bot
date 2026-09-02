"""
apps/notifications/tests/test_notifications.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import Channel, EventType, NotificationLog, NotificationPreference
from apps.notifications.services.notification_dispatcher import NotificationDispatcher

User = get_user_model()


class NotificationDispatcherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="negos", password="x", email="negos@example.com")
        self.dispatcher = NotificationDispatcher()

    def test_dispatch_without_user_only_logs_dashboard(self):
        logs = self.dispatcher.dispatch(EventType.NEW_SIGNAL, "BOOM1000 BUY")
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].channel, Channel.DASHBOARD)

    def test_dispatch_respects_disabled_preferences(self):
        NotificationPreference.objects.create(
            user=self.user, telegram_enabled=False, email_enabled=False,
        )
        logs = self.dispatcher.dispatch(EventType.NEW_SIGNAL, "BOOM1000 BUY", user=self.user)
        self.assertEqual(len(logs), 1)  # dashboard uniquement

    def test_dispatch_sends_email_when_enabled(self):
        NotificationPreference.objects.create(user=self.user, email_enabled=True)

        with patch(
            "apps.notifications.services.notification_dispatcher.EmailService.send",
            return_value=(True, ""),
        ) as mock_send:
            logs = self.dispatcher.dispatch(EventType.NEW_SIGNAL, "BOOM1000 BUY", user=self.user)

        mock_send.assert_called_once()
        channels = [log.channel for log in logs]
        self.assertIn(Channel.EMAIL, channels)

    def test_dispatch_sends_telegram_when_enabled(self):
        NotificationPreference.objects.create(user=self.user, telegram_enabled=True)

        with patch(
            "apps.notifications.services.notification_dispatcher.TelegramService.send",
            return_value=(True, ""),
        ) as mock_send:
            logs = self.dispatcher.dispatch(EventType.NEW_SIGNAL, "BOOM1000 BUY", user=self.user)

        mock_send.assert_called_once()
        channels = [log.channel for log in logs]
        self.assertIn(Channel.TELEGRAM, channels)

    def test_failed_telegram_send_is_logged_as_failure(self):
        NotificationPreference.objects.create(user=self.user, telegram_enabled=True)

        with patch(
            "apps.notifications.services.notification_dispatcher.TelegramService.send",
            return_value=(False, "chat_id manquant"),
        ):
            logs = self.dispatcher.dispatch(EventType.RISK_ALERT, "Stop trading", user=self.user)

        telegram_log = next(log for log in logs if log.channel == Channel.TELEGRAM)
        self.assertFalse(telegram_log.success)
        self.assertEqual(telegram_log.error_message, "chat_id manquant")

    def test_range_market_alert_respects_dedicated_preference(self):
        NotificationPreference.objects.create(
            user=self.user, email_enabled=True, notify_on_range_market=False,
        )
        logs = self.dispatcher.dispatch(EventType.RANGE_MARKET_ALERT, "Range détecté", user=self.user)
        self.assertEqual(len(logs), 1)  # email désactivé pour cet event -> dashboard only


class TelegramServiceTests(TestCase):
    def test_missing_token_returns_failure(self):
        from apps.notifications.services.telegram_service import TelegramService

        service = TelegramService(bot_token="")
        success, error = service.send("12345", "test")
        self.assertFalse(success)
        self.assertIn("TELEGRAM_BOT_TOKEN", error)


class EmailServiceTests(TestCase):
    def test_send_uses_django_console_backend(self):
        from django.core import mail

        from apps.notifications.services.email_service import EmailService

        service = EmailService()
        success, error = service.send("test@example.com", "Sujet", "Message")
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])

    def test_missing_recipient_fails_gracefully(self):
        from apps.notifications.services.email_service import EmailService

        service = EmailService()
        success, error = service.send("", "Sujet", "Message")
        self.assertFalse(success)
