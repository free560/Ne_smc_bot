"""
apps/settings_app/views.py

Page "hub" : pas de modèle dédié (les réglages vivent dans les apps
concernées - RiskSettings dans apps.risk, NotificationPreference dans
apps.notifications, UserProfile dans apps.accounts) pour éviter de
dupliquer l'état. Cette vue les rassemble et donne un accès rapide.
"""
from django.contrib.auth.decorators import login_required
from django.conf import settings as django_settings
from django.shortcuts import render

from apps.accounts.models import UserProfile
from apps.notifications.models import NotificationPreference
from apps.risk.models import RiskSettings


@login_required
def overview(request):
    risk_settings, _ = RiskSettings.objects.get_or_create(user=request.user)
    notification_preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    context = {
        "module_title": "Paramètres",
        "risk_settings": risk_settings,
        "notification_preference": notification_preference,
        "profile": profile,
        "trading_defaults": django_settings.TRADING_DEFAULTS,
    }
    return render(request, "settings_app/overview.html", context)
