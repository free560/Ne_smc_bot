"""
apps/accounts/models.py

On garde le User standard de Django (django.contrib.auth.User) et on
lui accroche un UserProfile (rôle, préférences de notification) plutôt
que de remplacer AUTH_USER_MODEL : plus simple à intégrer sans risque
de migration cassée sur un projet qui a déjà d'autres apps migrées.
"""
from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    TRADER = "TRADER", "Trader"
    VIEWER = "VIEWER", "Lecture seule"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.TRADER)
    telegram_chat_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def can_trade(self) -> bool:
        return self.role in (Role.ADMIN, Role.TRADER)


class AuditLog(models.Model):
    """Journal des actions sensibles : connexion, échec, scan manuel, changement de réglages..."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=64, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        who = self.user.username if self.user else "système"
        return f"[{self.action}] {who} ({self.created_at:%Y-%m-%d %H:%M:%S})"
