"""
apps/analytics/views.py
"""
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.analytics.services.analytics_service import AnalyticsService


@login_required
def overview(request):
    service = AnalyticsService()
    summary = service.compute_summary(request.user)
    signals_summary = service.signals_summary()

    context = {
        "module_title": "Analytics",
        "summary": summary,
        "signals_summary": signals_summary,
        "equity_curve_json": json.dumps(summary.equity_curve),
    }
    return render(request, "analytics/overview.html", context)
