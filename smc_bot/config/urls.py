"""
config/urls.py - Routes racine du projet SMC RSI BOOM & CRASH 1000 PRO BOT
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("market-data/", include("apps.market_data.urls")),
    path("scanner/", include("apps.scanner.urls")),
    path("signals/", include("apps.signals.urls")),
    path("journal/", include("apps.journal.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("risk/", include("apps.risk.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("settings/", include("apps.settings_app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
