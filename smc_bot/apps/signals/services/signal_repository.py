"""
apps/signals/services/signal_repository.py

Persiste les Signal (dataclasses produites par le DecisionEngine) sous
forme de SignalRecord (modèle Django), et permet de relire l'historique.
"""

from __future__ import annotations

from apps.signals.models import SignalRecord
from apps.signals.services.dtos import Signal


class SignalRepository:
    def save(self, signal: Signal) -> SignalRecord:
        obj, created = SignalRecord.objects.update_or_create(
            instrument=signal.instrument,
            direction=signal.direction.value,
            generated_at=signal.timestamp,
            defaults={
                "scenario": signal.scenario,
                "entry": signal.entry,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "risk_reward": signal.risk_reward,
                "confidence_score": signal.confidence_score,
                "reasons": signal.reasons,
            }
        )

        return obj
    def latest_for_instrument(self, instrument: str, limit: int = 20):
        return SignalRecord.objects.filter(instrument=instrument).order_by("-generated_at")[:limit]

    def latest_tradeable(self, limit: int = 20):
        return (
            SignalRecord.objects
            .exclude(direction="NO_TRADE")
            .order_by("-generated_at")[:limit]
        )

    def all_recent(self, limit: int = 50):
        return SignalRecord.objects.order_by("-generated_at")[:limit]
