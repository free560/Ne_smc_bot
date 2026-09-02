"""
apps/smc/services/fvg_engine.py

FAIR VALUE GAP ENGINE
-----------------------
Détecte les Fair Value Gaps (FVG) sur un motif de 3 bougies consécutives :
  - Bullish FVG : low de la bougie 3 > high de la bougie 1
    (la bougie 2, impulsive haussière, laisse un vide de prix)
  - Bearish FVG : high de la bougie 3 < low de la bougie 1
    (la bougie 2, impulsive baissière, laisse un vide de prix)
"""

from __future__ import annotations

from apps.smc.services.dtos import Candle, FairValueGap, TrendDirection


class FairValueGapEngine:
    def detect(self, candles: list[Candle]) -> list[FairValueGap]:
        gaps: list[FairValueGap] = []
        ordered = sorted(candles, key=lambda c: c.index)

        for i in range(len(ordered) - 2):
            c1, c2, c3 = ordered[i], ordered[i + 1], ordered[i + 2]

            # Bullish FVG : vide entre le high de c1 et le low de c3
            if c3.low > c1.high:
                gaps.append(FairValueGap(
                    direction=TrendDirection.BULLISH,
                    gap_top=c3.low,
                    gap_bottom=c1.high,
                    creation_index=c2.index,
                    creation_time=c2.timestamp,
                ))

            # Bearish FVG : vide entre le low de c1 et le high de c3
            if c3.high < c1.low:
                gaps.append(FairValueGap(
                    direction=TrendDirection.BEARISH,
                    gap_top=c1.low,
                    gap_bottom=c3.high,
                    creation_index=c2.index,
                    creation_time=c2.timestamp,
                ))

        return gaps

    def unfilled_gaps(self, gaps: list[FairValueGap], candles: list[Candle]) -> list[FairValueGap]:
        """Un FVG est considéré comme comblé si le prix est revenu totalement dedans."""
        unfilled = []
        for gap in gaps:
            filled = any(
                c.index > gap.creation_index and c.low <= gap.gap_bottom and c.high >= gap.gap_top
                for c in candles
            )
            if not filled:
                unfilled.append(gap)
        return unfilled
