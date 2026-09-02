"""
apps/market_data/services/candle_repository.py

Pont entre :
  - le stockage Django (models.Candle)
  - les dataclasses Python pures utilisées par le moteur SMC (apps.smc.services.dtos.Candle)

Toute lecture destinée au DecisionEngine passe par `get_engine_candles`,
qui réindexe les bougies (0..n-1, triées par temps croissant) comme
l'attendent les moteurs SMC.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.db import transaction

from apps.market_data.models import Candle as CandleModel
from apps.market_data.models import FetchLog, TimeframeChoice
from apps.market_data.services.deriv_client import DerivClient, RawCandle
from apps.smc.services.dtos import Candle as EngineCandle

logger = logging.getLogger("apps.market_data")

TIMEFRAME_TO_GRANULARITY = {
    TimeframeChoice.M1: 60,
    TimeframeChoice.M15: 900,
    TimeframeChoice.M30: 1800,
}


class CandleRepository:
    # ------------------------------------------------------------------
    # ÉCRITURE : sauvegarde des bougies brutes venant de Deriv
    # ------------------------------------------------------------------
    @transaction.atomic
    def save_raw_candles(self, instrument: str, timeframe: str, raw_candles: list[RawCandle]) -> int:
        """Upsert des bougies (idempotent grâce à la contrainte unique instrument+timeframe+epoch)."""
        saved = 0
        for rc in raw_candles:
            _, created = CandleModel.objects.update_or_create(
                instrument=instrument,
                timeframe=timeframe,
                epoch=rc.epoch,
                defaults={
                    "timestamp": datetime.fromtimestamp(rc.epoch, tz=timezone.utc),
                    "open": rc.open,
                    "high": rc.high,
                    "low": rc.low,
                    "close": rc.close,
                },
            )
            if created:
                saved += 1
        return saved

    # ------------------------------------------------------------------
    # RÉCUPÉRATION DEPUIS DERIV + SAUVEGARDE (avec journal)
    # ------------------------------------------------------------------
    def fetch_and_store(
        self, client: DerivClient, instrument: str, timeframe: str, count: int = 500
    ) -> int:
        granularity = TIMEFRAME_TO_GRANULARITY[timeframe]
        log_entry = FetchLog(instrument=instrument, timeframe=timeframe, requested_count=count)

        try:
            raw_candles = client.fetch_candles(instrument, granularity, count)
            saved = self.save_raw_candles(instrument, timeframe, raw_candles)
            log_entry.fetched_count = len(raw_candles)
            log_entry.success = True
            log_entry.save()
            return saved
        except Exception as exc:  # noqa: BLE001 - on journalise tout, on ne masque rien
            log_entry.success = False
            log_entry.error_message = str(exc)
            log_entry.save()
            logger.error("Échec fetch_and_store(%s, %s) : %s", instrument, timeframe, exc)
            raise

    # ------------------------------------------------------------------
    # LECTURE POUR LE MOTEUR SMC
    # ------------------------------------------------------------------
    def get_engine_candles(self, instrument: str, timeframe: str, limit: int = 200) -> list[EngineCandle]:
        """
        Renvoie les `limit` dernières bougies en base, triées du plus ancien
        au plus récent, réindexées 0..n-1 comme l'attendent les moteurs SMC.
        """
        queryset = (
            CandleModel.objects
            .filter(instrument=instrument, timeframe=timeframe)
            .order_by("-timestamp")[:limit]
        )
        rows = list(reversed(queryset))  # remet en ordre chronologique croissant

        return [
            EngineCandle(
                index=i,
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for i, row in enumerate(rows)
        ]

    def latest_timestamp(self, instrument: str, timeframe: str) -> datetime | None:
        row = (
            CandleModel.objects
            .filter(instrument=instrument, timeframe=timeframe)
            .order_by("-timestamp")
            .first()
        )
        return row.timestamp if row else None
