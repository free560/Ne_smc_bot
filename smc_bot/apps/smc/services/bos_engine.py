"""
apps/smc/services/bos_engine.py

BOS ENGINE
----------
Détecte les cassures de structure (Break of Structure) :
  - BOS haussier : clôture au-dessus du dernier swing high significatif
    pendant une structure déjà (ou en train de devenir) haussière.
  - BOS baissier : clôture en dessous du dernier swing low significatif
    pendant une structure déjà (ou en train de devenir) baissière.

Validation possible sur M30 et M15 (voir DecisionEngine pour la
combinaison des deux timeframes).
"""

from __future__ import annotations

from apps.smc.services.dtos import (
    BOSEvent,
    Candle,
    StructureState,
    SwingType,
    Timeframe,
    TrendDirection,
)


class BOSEngine:
    def detect(self, candles: list[Candle], structure: StructureState) -> list[BOSEvent]:
        """
        Parcourt les bougies après chaque swing connu et vérifie si la
        clôture casse le niveau du swing opposé au sens de la cassure :
          - une clôture > dernier swing high  => BOS haussier
          - une clôture < dernier swing low   => BOS baissier
        On ne garde que les BOS "frais" (pas déjà cassés plusieurs fois de suite).
        """
        events: list[BOSEvent] = []

        highs = [s for s in structure.swings if s.swing_type == SwingType.HIGH]
        lows = [s for s in structure.swings if s.swing_type == SwingType.LOW]

        broken_high_indices: set[int] = set()
        broken_low_indices: set[int] = set()

        for candle in candles:
            # BOS haussier : clôture au-dessus d'un swing high pas encore cassé
            for high in highs:
                if high.candle_index in broken_high_indices:
                    continue
                if candle.index > high.candle_index and candle.close > high.price:
                    events.append(BOSEvent(
                        timeframe=structure.timeframe,
                        direction=TrendDirection.BULLISH,
                        break_price=candle.close,
                        broken_swing=high,
                        candle_index=candle.index,
                        timestamp=candle.timestamp,
                    ))
                    broken_high_indices.add(high.candle_index)

            # BOS baissier : clôture en dessous d'un swing low pas encore cassé
            for low in lows:
                if low.candle_index in broken_low_indices:
                    continue
                if candle.index > low.candle_index and candle.close < low.price:
                    events.append(BOSEvent(
                        timeframe=structure.timeframe,
                        direction=TrendDirection.BEARISH,
                        break_price=candle.close,
                        broken_swing=low,
                        candle_index=candle.index,
                        timestamp=candle.timestamp,
                    ))
                    broken_low_indices.add(low.candle_index)

        events.sort(key=lambda e: e.candle_index)
        return events

    def last_bos(self, events: list[BOSEvent]) -> BOSEvent | None:
        return events[-1] if events else None

    def is_valid_on(self, events: list[BOSEvent], direction: TrendDirection, timeframe: Timeframe) -> bool:
        """True si le dernier BOS du timeframe donné va dans `direction`."""
        matching = [e for e in events if e.timeframe == timeframe]
        last = self.last_bos(matching)
        return last is not None and last.direction == direction
