"""
apps/market_data/tasks.py

Tâche Celery pour maintenir la base de bougies à jour depuis Deriv.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from apps.market_data.models import Instrument, TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.market_data.services.deriv_client import DerivClient

logger = logging.getLogger("apps.market_data")


@shared_task
def fetch_all_candles_task(count: int = 500) -> dict:
    if not settings.DERIV_APP_ID:
        logger.error("DERIV_APP_ID non configuré - impossible de lancer fetch_all_candles_task")
        return {"error": "DERIV_APP_ID manquant"}

    client = DerivClient(
        app_id=settings.DERIV_APP_ID,
        api_token=settings.DERIV_API_TOKEN,
        ws_url=settings.DERIV_WS_URL,
    )
    repository = CandleRepository()
    results = {}

    for instrument in Instrument.values:
        for timeframe in TimeframeChoice.values:
            key = f"{instrument}_{timeframe}"
            try:
                saved = repository.fetch_and_store(client, instrument, timeframe, count=count)
                results[key] = {"saved": saved}
            except Exception as exc:  # noqa: BLE001
                results[key] = {"error": str(exc)}

    return results
