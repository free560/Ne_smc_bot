"""
apps/accounts/signals.py

- Crée automatiquement un UserProfile à la création d'un User.
- Journalise les connexions/déconnexions dans l'AuditLog.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import UserProfile
from apps.accounts.services.audit_service import AuditService

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditService.log("LOGIN", user=user, ip_address=_client_ip(request))


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    AuditService.log("LOGOUT", user=user, ip_address=_client_ip(request))


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request=None, **kwargs):
    AuditService.log(
        "LOGIN_FAILED",
        user=None,
        details={"username": credentials.get("username", "")},
        ip_address=_client_ip(request) if request else None,
    )


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
