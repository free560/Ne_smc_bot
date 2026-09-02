"""
apps/accounts/views.py
"""
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import AuditLog


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"


class LogoutView(auth_views.LogoutView):
    next_page = "accounts:login"


@login_required
def audit_log(request):
    logs = AuditLog.objects.select_related("user")[:100]
    context = {"module_title": "Journal d'audit", "logs": logs}
    return render(request, "accounts/audit_log.html", context)
