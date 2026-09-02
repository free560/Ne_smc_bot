"""
apps/smc/services/choch_engine.py

CHOCH ENGINE
------------
Détecte les changements de caractère (Change of Character) :
  - CHoCH haussier : en structure baissière, le prix casse le dernier
    Lower High (LH) => premier signe de retournement vers le haut.
  - CHoCH baissier : en structure haussière, le prix casse le dernier
    Higher Low (HL) => premier signe de retournement vers le bas.

Contrairement au BOS (qui confirme la tendance en cours), le CHoCH
signale une rupture potentielle de cette tendance.
"""

from __future__ import annotations

from apps.smc.services.dtos import (
    Candle,
    CHoCHEvent,
    StructureLabel,
    StructureState,
    SwingType,
    Timeframe,
    TrendDirection,
)


class CHoCHEngine:
    def detect(self, candles: list[Candle], structure: StructureState) -> list[CHoCHEvent]:
        events: list[CHoCHEvent] = []

        lows = [s for s in structure.swings if s.swing_type == SwingType.LOW]
        highs = [s for s in structure.swings if s.swing_type == SwingType.HIGH]

        broken_hl: set[int] = set()
        broken_lh: set[int] = set()

        for candle in candles:
            # CHoCH baissier : cassure d'un Higher Low (HL) en structure haussière
            for low in lows:
                if low.label != StructureLabel.HL or low.candle_index in broken_hl:
                    continue
                if candle.index > low.candle_index and candle.close < low.price:
                    strength = self._compute_strength(candle, low.price)
                    events.append(CHoCHEvent(
                        timeframe=structure.timeframe,
                        direction=TrendDirection.BEARISH,
                        price=candle.close,
                        candle_index=candle.index,
                        timestamp=candle.timestamp,
                        strength=strength,
                    ))
                    broken_hl.add(low.candle_index)

            # CHoCH haussier : cassure d'un Lower High (LH) en structure baissière
            for high in highs:
                if high.label != StructureLabel.LH or high.candle_index in broken_lh:
                    continue
                if candle.index > high.candle_index and candle.close > high.price:
                    strength = self._compute_strength(candle, high.price)
                    events.append(CHoCHEvent(
                        timeframe=structure.timeframe,
                        direction=TrendDirection.BULLISH,
                        price=candle.close,
                        candle_index=candle.index,
                        timestamp=candle.timestamp,
                        strength=strength,
                    ))
                    broken_lh.add(high.candle_index)

        events.sort(key=lambda e: e.candle_index)
        return events

    @staticmethod
    def _compute_strength(breaking_candle: Candle, broken_level: float) -> float:
        """
        Score 0-100 basé sur l'amplitude de la cassure relativement au range
        de la bougie qui casse. Une cassure nette (grosse bougie, clôture loin
        du niveau cassé) donne un CHoCH plus "fort".
        """
        if breaking_candle.range_size == 0:
            return 0.0
        distance = abs(breaking_candle.close - broken_level)
        ratio = distance / breaking_candle.range_size
        return round(min(ratio, 1.0) * 100, 2)

    def last_choch(self, events: list[CHoCHEvent]) -> CHoCHEvent | None:
        return events[-1] if events else None
