"""
apps/smc/tests/factories.py

Générateur de bougies synthétiques pour les tests unitaires des moteurs SMC.
Pas de dépendance Django : ce sont des objets Python purs (voir dtos.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from apps.smc.services.dtos import Candle


def make_candles(closes: list[float], start: datetime | None = None, minutes_step: int = 1,
                  wick_ratio: float = 0.15) -> list[Candle]:
    """
    Construit une liste de Candle à partir d'une simple liste de closes.
    open[i] = close[i-1] (sauf la première), high/low ajoutent un petit wick
    proportionnel au mouvement pour que les fractales soient détectables.
    """
    start = start or datetime(2026, 1, 1, 0, 0, 0)
    candles: list[Candle] = []
    prev_close = closes[0]

    for i, close in enumerate(closes):
        open_price = prev_close if i > 0 else close
        body_high = max(open_price, close)
        body_low = min(open_price, close)
        body_range = max(body_high - body_low, 0.01)
        wick = body_range * wick_ratio

        candles.append(Candle(
            index=i,
            timestamp=start + timedelta(minutes=minutes_step * i),
            open=open_price,
            high=body_high + wick,
            low=body_low - wick,
            close=close,
        ))
        prev_close = close

    return candles
