"""
apps/market_data/views.py
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.market_data.models import FetchLog


@login_required
def overview(request):
    logs = FetchLog.objects.all()[:100]
    context = {"module_title": "Market Data", "logs": logs}
    return render(request, "market_data/overview.html", context)
