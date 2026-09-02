"""
apps/dashboard/views.py
"""
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.indicators.services.rsi_engine import RSIEngine
from apps.market_data.models import Instrument, TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.signals.models import SignalRecord
from apps.signals.services.signal_repository import SignalRepository


@login_required
def overview(request):
    candle_repo = CandleRepository()
    signal_repo = SignalRepository()
    rsi_engine = RSIEngine(period=14)

    instrument = request.GET.get("instrument", Instrument.BOOM1000.value)
    if instrument not in [c.value for c in Instrument]:
        instrument = Instrument.BOOM1000.value

    m1_candles = candle_repo.get_engine_candles(instrument, TimeframeChoice.M1, limit=100)
    rsi_series = rsi_engine.compute_series(m1_candles)
    rsi_by_index = {r.candle_index: r.value for r in rsi_series}

    chart_data = {
        "labels": [c.timestamp.strftime("%H:%M") for c in m1_candles],
        "prices": [c.close for c in m1_candles],
        "rsi": [rsi_by_index.get(c.index) for c in m1_candles],
    }

    stats = {
        "total_signals": SignalRecord.objects.count(),
        "buy_signals": SignalRecord.objects.filter(direction="BUY").count(),
        "sell_signals": SignalRecord.objects.filter(direction="SELL").count(),
        "no_trade_signals": SignalRecord.objects.filter(direction="NO_TRADE").count(),
    }

    context = {
        "module_title": "Vue d'ensemble",
        "instruments": Instrument.choices,
        "selected_instrument": instrument,
        "stats": stats,
        "latest_signals": signal_repo.latest_for_instrument(instrument, limit=5),
        "chart_data_json": json.dumps(chart_data),
        "has_candles": bool(m1_candles),
    }
    return render(request, "dashboard/overview.html", context)
