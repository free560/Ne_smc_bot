"""
apps/journal/models.py

Journal de trading : chaque entrée correspond à un trade réellement
exécuté par l'utilisateur (manuellement, suite à un signal ou non).
Optionnellement lié au SignalRecord qui a motivé le trade.
"""
from django.conf import settings
from django.db import models

from apps.market_data.models import Instrument


class TradeResult(models.TextChoices):
    OPEN = "OPEN", "Ouvert"
    WIN = "WIN", "Gagnant"
    LOSS = "LOSS", "Perdant"
    BREAKEVEN = "BREAKEVEN", "Break-even"


class TradeJournalEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journal_entries")
    signal = models.ForeignKey(
        "signals.SignalRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries"
    )

    instrument = models.CharField(max_length=16, choices=Instrument.choices)
    direction = models.CharField(max_length=8, choices=[("BUY", "Achat"), ("SELL", "Vente")])

    entry = models.FloatField()
    stop_loss = models.FloatField()
    take_profit = models.FloatField()
    lot_size = models.FloatField(default=0.01)

    result = models.CharField(max_length=16, choices=TradeResult.choices, default=TradeResult.OPEN)
    pnl = models.FloatField(null=True, blank=True, help_text="Profit/perte réalisé, renseigné à la clôture")

    screenshot = models.ImageField(upload_to="journal_screenshots/", null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [models.Index(fields=["user", "instrument", "result"])]

    def __str__(self):
        return f"{self.instrument} {self.direction} - {self.result} ({self.opened_at:%Y-%m-%d})"

    @property
    def is_closed(self) -> bool:
        return self.result != TradeResult.OPEN

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.stop_loss)
        reward = abs(self.take_profit - self.entry)
        return round(reward / risk, 2) if risk else 0.0
