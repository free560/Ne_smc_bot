"""
apps/signals/models.py

Persistance des signaux générés par le DecisionEngine (apps.signals.services).
Chaque exécution du scanner sur un instrument crée un SignalRecord,
qu'il soit tradeable (BUY/SELL) ou NO_TRADE (pour garder un historique complet).
"""
from django.db import models

from apps.market_data.models import Instrument


class DirectionChoice(models.TextChoices):
    BUY = "BUY", "Achat"
    SELL = "SELL", "Vente"
    NO_TRADE = "NO_TRADE", "Pas de trade"


class SignalRecord(models.Model):
    instrument = models.CharField(max_length=16, choices=Instrument.choices, db_index=True)
    direction = models.CharField(max_length=8, choices=DirectionChoice.choices, db_index=True)
    scenario = models.CharField(max_length=32, blank=True, null=True)

    entry = models.FloatField(null=True, blank=True)
    stop_loss = models.FloatField(null=True, blank=True)
    take_profit = models.FloatField(null=True, blank=True)
    risk_reward = models.FloatField(null=True, blank=True)
    confidence_score = models.IntegerField(default=0)

    reasons = models.JSONField(default=list, blank=True)

    generated_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["instrument", "direction", "generated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "direction", "generated_at"],
                name="unique_signal_record"
            )
        ]

    def __str__(self):
        return f"{self.instrument} {self.direction} ({self.generated_at:%Y-%m-%d %H:%M})"

    @property
    def is_tradeable(self) -> bool:
        return self.direction != DirectionChoice.NO_TRADE
