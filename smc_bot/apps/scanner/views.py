"""
apps/scanner/views.py
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.market_data.models import Instrument, TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.scanner.services.scanner_service import InsufficientDataError, ScannerService


@login_required
def overview(request):
    repository = CandleRepository()

    status = []
    for instrument in Instrument.values:
        row = {
            "instrument": instrument,
            "timeframes": [(tf, repository.latest_timestamp(instrument, tf)) for tf in TimeframeChoice.values],
        }
        status.append(row)

    context = {
        "module_title": "Scanner de Marché",
        "status": status,
        "timeframes": TimeframeChoice.values,
    }
    return render(request, "scanner/overview.html", context)


@login_required
def trigger_scan(request):
    service = ScannerService()
    errors = []
    for instrument in Instrument.values:
        try:
            service.scan_instrument(instrument)
        except InsufficientDataError as exc:
            errors.append(str(exc))

    return redirect("scanner:overview")
