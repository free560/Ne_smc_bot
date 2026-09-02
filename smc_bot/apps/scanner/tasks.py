"""
apps/scanner/tasks.py

Tâches Celery pour l'exécution périodique du scanner.
Activées en production via `app.conf.beat_schedule` (config/celery.py)
une fois Redis + les credentials Deriv en place.
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.scanner.services.scanner_service import InsufficientDataError, ScannerService

logger = logging.getLogger("apps.scanner")


@shared_task
def scan_instrument_task(instrument: str) -> dict:
    service = ScannerService()
    try:
        signal = service.scan_instrument(instrument)
        return signal.to_dict()
    except InsufficientDataError as exc:
        logger.warning(str(exc))
        return {"instrument": instrument, "error": str(exc)}


@shared_task
def scan_all_instruments() -> list[dict]:
    service = ScannerService()
    results = service.scan_all()
    return [signal.to_dict() if signal else {"instrument": name, "error": "insufficient_data"}
            for name, signal in results.items()]
