"""
apps/notifications/models.py

NotificationPreference : canaux activés par utilisateur (Telegram/Email).
NotificationLog        : historique de toutes les notifications envoyées
                          (ou tentées), consultable dans le module Notifications.
"""
from django.conf import settings
from django.db import models


class EventType(models.TextChoices):
    NEW_SIGNAL = "NEW_SIGNAL", "Nouveau signal"
    RISK_ALERT = "RISK_ALERT", "Alerte risque"
    DRAWDOWN_ALERT = "DRAWDOWN_ALERT", "Alerte drawdown"
    CONSECUTIVE_LOSS_ALERT = "CONSECUTIVE_LOSS_ALERT", "Pertes consécutives"
    RANGE_MARKET_ALERT = "RANGE_MARKET_ALERT", "Marché en range"


class Channel(models.TextChoices):
    DASHBOARD = "DASHBOARD", "Dashboard"
    TELEGRAM = "TELEGRAM", "Telegram"
    EMAIL = "EMAIL", "Email"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    telegram_enabled = models.BooleanField(default=False)
    email_enabled = models.BooleanField(default=False)
    email_override = models.EmailField(blank=True, default="", help_text="Laisser vide pour utiliser l'email du compte")

    notify_on_signal = models.BooleanField(default=True)
    notify_on_risk_alert = models.BooleanField(default=True)
    notify_on_range_market = models.BooleanField(default=False)

    def __str__(self):
        return f"Préférences notifications de {self.user.username}"

    @property
    def resolved_email(self) -> str:
        return self.email_override or self.user.email


class NotificationLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    message = models.TextField()
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.channel}] {self.event_type} ({self.created_at:%Y-%m-%d %H:%M})"
