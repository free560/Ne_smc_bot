"""
apps/signals/views.py

Vues fines : toute la logique (lecture, filtrage) reste dans
apps.signals.services / apps.scanner.services. La vue ne fait
qu'orchestrer service -> template.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.market_data.models import Instrument
from apps.scanner.services.scanner_service import InsufficientDataError, ScannerService
from apps.signals.services.signal_repository import SignalRepository


@login_required
def overview(request):
    repository = SignalRepository()
    instrument_filter = request.GET.get("instrument")

    if instrument_filter in [c.value for c in Instrument]:
        records = repository.latest_for_instrument(instrument_filter, limit=50)
    else:
        records = repository.all_recent(limit=50)

    context = {
        "module_title": "Centre de Signaux",
        "records": records,
        "instruments": Instrument.choices,
        "selected_instrument": instrument_filter,
    }
    return render(request, "signals/overview.html", context)


@login_required
def run_scan_now(request):
    """Déclenche un scan à la demande (bouton 'Scanner maintenant' du dashboard)."""
    service = ScannerService()
    errors = []

    for instrument in [c.value for c in Instrument]:
        try:
            service.scan_instrument(instrument)
        except InsufficientDataError as exc:
            errors.append(str(exc))

    repository = SignalRepository()
    context = {
        "module_title": "Centre de Signaux",
        "records": repository.all_recent(limit=50),
        "instruments": Instrument.choices,
        "selected_instrument": None,
        "scan_errors": errors,
        "scan_triggered": True,
    }
    return render(request, "signals/overview.html", context)
