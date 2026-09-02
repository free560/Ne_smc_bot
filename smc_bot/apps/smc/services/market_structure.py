"""
apps/smc/services/market_structure.py

MARKET STRUCTURE ENGINE
------------------------
Détecte les points pivots (swing highs / swing lows) sur une série de
bougies, les classifie en HH / HL / LH / LL, et en déduit la tendance :
BULLISH, BEARISH ou RANGE.
"""

from __future__ import annotations

from apps.smc.services.dtos import (
    Candle,
    StructureLabel,
    StructureState,
    SwingPoint,
    SwingType,
    Timeframe,
    TrendDirection,
)


class MarketStructureEngine:
    """
    Détection de structure par la méthode des fractales :
    une bougie est un swing high si son `high` est strictement supérieur
    à celui des `lookback` bougies avant ET après elle (symétrique).
    Idem pour un swing low avec le `low`.
    """

    def __init__(self, lookback: int = 2):
        if lookback < 1:
            raise ValueError("lookback doit être >= 1")
        self.lookback = lookback

    # ------------------------------------------------------------------
    # DÉTECTION DES SWINGS
    # ------------------------------------------------------------------
    def find_swing_points(self, candles: list[Candle]) -> list[SwingPoint]:
        n = len(candles)
        lb = self.lookback
        swings: list[SwingPoint] = []

        for i in range(lb, n - lb):
            window = candles[i - lb: i + lb + 1]
            current = candles[i]

            if current.high == max(c.high for c in window):
                swings.append(SwingPoint(
                    candle_index=current.index,
                    timestamp=current.timestamp,
                    price=current.high,
                    swing_type=SwingType.HIGH,
                ))

            if current.low == min(c.low for c in window):
                swings.append(SwingPoint(
                    candle_index=current.index,
                    timestamp=current.timestamp,
                    price=current.low,
                    swing_type=SwingType.LOW,
                ))

        swings.sort(key=lambda s: s.candle_index)
        return swings

    # ------------------------------------------------------------------
    # CLASSIFICATION HH / HL / LH / LL
    # ------------------------------------------------------------------
    def classify_swings(self, swings: list[SwingPoint]) -> list[SwingPoint]:
        """
        Compare chaque swing au précédent swing du même type
        (high vs high précédent, low vs low précédent) pour lui
        attribuer un label HH / HL / LH / LL.
        """
        classified: list[SwingPoint] = []
        last_high: SwingPoint | None = None
        last_low: SwingPoint | None = None

        for swing in swings:
            if swing.swing_type == SwingType.HIGH:
                if last_high is None:
                    label = None
                else:
                    label = StructureLabel.HH if swing.price > last_high.price else StructureLabel.LH
                last_high = swing
            else:
                if last_low is None:
                    label = None
                else:
                    label = StructureLabel.HL if swing.price > last_low.price else StructureLabel.LL
                last_low = swing

            classified.append(SwingPoint(
                candle_index=swing.candle_index,
                timestamp=swing.timestamp,
                price=swing.price,
                swing_type=swing.swing_type,
                label=label,
            ))

        return classified

    # ------------------------------------------------------------------
    # TENDANCE
    # ------------------------------------------------------------------
    def determine_trend(self, classified_swings: list[SwingPoint]) -> TrendDirection:
        """
        Règle :
          - Bullish  : les 2 derniers labels de haut ET de bas les plus récents
                       forment HH + HL
          - Bearish  : LH + LL
          - Sinon    : RANGE (structure indécise / pas assez de données)
        """
        highs = [s for s in classified_swings if s.swing_type == SwingType.HIGH and s.label]
        lows = [s for s in classified_swings if s.swing_type == SwingType.LOW and s.label]

        if not highs or not lows:
            return TrendDirection.RANGE

        last_high_label = highs[-1].label
        last_low_label = lows[-1].label

        if last_high_label == StructureLabel.HH and last_low_label == StructureLabel.HL:
            return TrendDirection.BULLISH
        if last_high_label == StructureLabel.LH and last_low_label == StructureLabel.LL:
            return TrendDirection.BEARISH
        return TrendDirection.RANGE

    # ------------------------------------------------------------------
    # PIPELINE COMPLET
    # ------------------------------------------------------------------
    def analyze(self, candles: list[Candle], timeframe: Timeframe) -> StructureState:
        """Point d'entrée principal : renvoie un StructureState complet."""
        raw_swings = self.find_swing_points(candles)
        classified = self.classify_swings(raw_swings)
        trend = self.determine_trend(classified)
        return StructureState(timeframe=timeframe, swings=classified, trend=trend)
