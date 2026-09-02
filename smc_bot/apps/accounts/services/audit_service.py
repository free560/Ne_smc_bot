"""
apps/accounts/services/audit_service.py

Service centralisé d'écriture dans le journal d'audit. Les autres apps
(scanner, risk, journal, settings_app...) appellent `AuditService.log(...)`
plutôt que d'écrire directement dans le modèle AuditLog.
"""

from __future__ import annotations

from apps.accounts.models import AuditLog


class AuditService:
    @staticmethod
    def log(action: str, user=None, details: dict | None = None, ip_address: str | None = None) -> AuditLog:
        return AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            details=details or {},
            ip_address=ip_address,
        )
