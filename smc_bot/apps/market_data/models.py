"""
apps/market_data/models.py

Persistance des bougies OHLC récupérées depuis l'API Deriv.
Une ligne = une bougie pour un instrument + un timeframe donnés.
"""
from django.db import models


class Instrument(models.TextChoices):
    BOOM1000 = "BOOM1000", "Boom 1000"
    CRASH1000 = "CRASH1000", "Crash 1000"


class TimeframeChoice(models.TextChoices):
    M1 = "M1", "1 minute"
    M15 = "M15", "15 minutes"
    M30 = "M30", "30 minutes"


# Granularité Deriv (en secondes) pour chaque timeframe - utilisé par le client WebSocket.
TIMEFRAME_GRANULARITY_SECONDS = {
    TimeframeChoice.M1: 60,
    TimeframeChoice.M15: 900,
    TimeframeChoice.M30: 1800,
}


class Candle(models.Model):
    """Une bougie OHLC persistée, identifiée par (instrument, timeframe, epoch)."""

    instrument = models.CharField(max_length=16, choices=Instrument.choices, db_index=True)
    timeframe = models.CharField(max_length=4, choices=TimeframeChoice.choices, db_index=True)

    epoch = models.BigIntegerField(help_text="Timestamp Unix (secondes) fourni par Deriv")
    timestamp = models.DateTimeField(db_index=True)

    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "timeframe", "epoch"],
                name="unique_candle_per_instrument_timeframe_epoch",
            )
        ]
        indexes = [
            models.Index(fields=["instrument", "timeframe", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.instrument} {self.timeframe} @ {self.timestamp:%Y-%m-%d %H:%M} = {self.close}"


class FetchLog(models.Model):
    """Journal des tentatives de récupération de données (utile pour debug réseau)."""

    instrument = models.CharField(max_length=16, choices=Instrument.choices)
    timeframe = models.CharField(max_length=4, choices=TimeframeChoice.choices)
    requested_count = models.IntegerField()
    fetched_count = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        status = "OK" if self.success else "ÉCHEC"
        return f"[{status}] {self.instrument} {self.timeframe} ({self.created_at:%Y-%m-%d %H:%M:%S})"
