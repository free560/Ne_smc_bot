"""
apps/scanner/services/scanner_service.py

SCANNER SERVICE
----------------
Orchestre un scan complet pour un instrument :
  1. Lit les bougies M30/M15/M1 déjà en base (via CandleRepository)
  2. Les passe au DecisionEngine (apps.signals)
  3. Persiste le Signal résultant (via SignalRepository)
  4. Renvoie le Signal pour un usage immédiat (notification, affichage...)

Ne fait PAS l'appel réseau à Deriv lui-même : c'est le rôle de
`fetch_candles` (management command / tâche Celery dédiée) de tenir
la base à jour. Séparer les deux évite qu'un scan de signal soit
bloqué par une lenteur/erreur réseau.
"""

from __future__ import annotations

import logging

from apps.market_data.models import TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.signals.services.decision_engine import DecisionEngine
from apps.signals.services.dtos import Signal
from apps.signals.services.signal_repository import SignalRepository

logger = logging.getLogger("apps.scanner")

MIN_CANDLES_REQUIRED = 30  # en dessous, pas assez de données pour une analyse fiable


class InsufficientDataError(Exception):
    """Levée quand il n'y a pas assez de bougies en base pour lancer une analyse."""


class ScannerService:
    def __init__(
        self,
        candle_repository: CandleRepository | None = None,
        signal_repository: SignalRepository | None = None,
        decision_engine: DecisionEngine | None = None,
        notify: bool = True,
    ):
        self.candle_repository = candle_repository or CandleRepository()
        self.signal_repository = signal_repository or SignalRepository()
        self.decision_engine = decision_engine or DecisionEngine()
        self.notify = notify

    def scan_instrument(self, instrument: str, persist: bool = True) -> Signal:
        m30 = self.candle_repository.get_engine_candles(instrument, TimeframeChoice.M30, limit=200)
        m15 = self.candle_repository.get_engine_candles(instrument, TimeframeChoice.M15, limit=200)
        m1 = self.candle_repository.get_engine_candles(instrument, TimeframeChoice.M1, limit=200)

        if len(m30) < MIN_CANDLES_REQUIRED or len(m15) < MIN_CANDLES_REQUIRED or len(m1) < MIN_CANDLES_REQUIRED:
            raise InsufficientDataError(
                f"Pas assez de données pour {instrument} "
                f"(M30={len(m30)}, M15={len(m15)}, M1={len(m1)}, minimum={MIN_CANDLES_REQUIRED}). "
                "Lance d'abord `python manage.py fetch_candles --all`."
            )

        signal = self.decision_engine.generate_signal(instrument, m30, m15, m1)

        if persist:
            self.signal_repository.save(signal)

        if signal.is_tradeable:
            logger.info("Signal %s généré pour %s (confiance %s%%)",
                        signal.direction.value, instrument, signal.confidence_score)
            if self.notify:
                self._broadcast("NEW_SIGNAL",
                                 f"{instrument} : {signal.direction.value} ({signal.scenario}, "
                                 f"confiance {signal.confidence_score}%)")
        elif self.notify and signal.scenario == "RANGE_FILTER":
            self._broadcast("RANGE_MARKET_ALERT", f"{instrument} : marché en range, pas de signal")

        return signal

    def scan_all(self, instruments: list[str] | None = None) -> dict[str, Signal | None]:
        from apps.market_data.models import Instrument as InstrumentChoice

        instruments = instruments or [c.value for c in InstrumentChoice]
        results: dict[str, Signal | None] = {}

        for instrument in instruments:
            try:
                results[instrument] = self.scan_instrument(instrument)
            except InsufficientDataError as exc:
                logger.warning(str(exc))
                results[instrument] = None

        return results

    # ------------------------------------------------------------------
    @staticmethod
    def _broadcast(event_type: str, message: str) -> None:
        """Notifie tous les utilisateurs ayant activé un canal pour cet événement."""
        from django.contrib.auth import get_user_model

        from apps.notifications.services.notification_dispatcher import NotificationDispatcher

        dispatcher = NotificationDispatcher()
        User = get_user_model()
        for user in User.objects.filter(is_active=True):
            dispatcher.dispatch(event_type, message, user=user)
