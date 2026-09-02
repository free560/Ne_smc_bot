"""
apps/indicators/services/rsi_engine.py

RSI ENGINE
----------
Calcule le RSI (Relative Strength Index) selon la méthode originale de
Wilder (moyenne mobile lissée), utilisé en confirmation sur M1.

Formule :
    RS  = moyenne des hausses / moyenne des baisses (sur `period` bougies)
    RSI = 100 - (100 / (1 + RS))
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.smc.services.dtos import Candle


@dataclass(frozen=True)
class RSIValue:
    candle_index: int
    value: float


class RSIEngine:
    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period doit être >= 1")
        self.period = period

    def compute_series(self, candles: list[Candle]) -> list[RSIValue]:
        """
        Calcule le RSI pour toute la série (lissage de Wilder).
        Renvoie une liste vide si pas assez de bougies (< period + 1).
        """
        ordered = sorted(candles, key=lambda c: c.index)
        if len(ordered) < self.period + 1:
            return []

        closes = [c.close for c in ordered]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        gains = [max(d, 0.0) for d in deltas]
        losses = [max(-d, 0.0) for d in deltas]

        avg_gain = sum(gains[: self.period]) / self.period
        avg_loss = sum(losses[: self.period]) / self.period

        results: list[RSIValue] = []
        # premier point RSI, aligné sur la bougie period+1 (index dans `ordered`)
        results.append(RSIValue(
            candle_index=ordered[self.period].index,
            value=self._rsi_from_averages(avg_gain, avg_loss),
        ))

        for i in range(self.period, len(deltas)):
            avg_gain = (avg_gain * (self.period - 1) + gains[i]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i]) / self.period
            results.append(RSIValue(
                candle_index=ordered[i + 1].index,
                value=self._rsi_from_averages(avg_gain, avg_loss),
            ))

        return results

    @staticmethod
    def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    def latest(self, candles: list[Candle]) -> RSIValue | None:
        series = self.compute_series(candles)
        return series[-1] if series else None

    # ------------------------------------------------------------------
    # Seuils de la stratégie SMC RSI BOOM & CRASH 1000 PRO
    # ------------------------------------------------------------------
    @staticmethod
    def is_oversold(rsi_value: float, threshold: float = 15.0) -> bool:
        return rsi_value <= threshold

    @staticmethod
    def is_overbought(rsi_value: float, threshold: float = 85.0) -> bool:
        return rsi_value >= threshold

    @staticmethod
    def oversold_strength(rsi_value: float) -> str:
        """Retourne le palier atteint : '<=15', '<=10', '<=1', ou None."""
        if rsi_value <= 1:
            return "<=1"
        if rsi_value <= 10:
            return "<=10"
        if rsi_value <= 15:
            return "<=15"
        return None

    @staticmethod
    def overbought_strength(rsi_value: float) -> str:
        """Retourne le palier atteint : '>=85', '>=90', '>=98', ou None."""
        if rsi_value >= 98:
            return ">=98"
        if rsi_value >= 90:
            return ">=90"
        if rsi_value >= 85:
            return ">=85"
        return None
