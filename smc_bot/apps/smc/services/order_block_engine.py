"""
apps/smc/services/order_block_engine.py

ORDER BLOCK ENGINE
-------------------
Détecte les Order Blocks (dernière bougie opposée avant un mouvement
impulsif qui produit un BOS) :
  - Bullish Order Block : dernière bougie BAISSIÈRE avant un mouvement
    haussier qui casse la structure (BOS haussier).
  - Bearish Order Block : dernière bougie HAUSSIÈRE avant un mouvement
    baissier qui casse la structure (BOS baissier).

Le statut (UNMITIGATED / MITIGATED / INVALIDATED) est recalculé à
chaque nouvelle bougie via `update_status`.
"""

from __future__ import annotations

from apps.smc.services.dtos import (
    BOSEvent,
    Candle,
    OrderBlock,
    OrderBlockStatus,
    TrendDirection,
)


class OrderBlockEngine:
    def detect(self, candles: list[Candle], bos_events: list[BOSEvent]) -> list[OrderBlock]:
        order_blocks: list[OrderBlock] = []
        candles_by_index = {c.index: c for c in candles}

        for bos in bos_events:
            origin_candle = self._find_origin_candle(candles, bos)
            if origin_candle is None:
                continue

            order_blocks.append(OrderBlock(
                direction=bos.direction,
                zone_high=origin_candle.high,
                zone_low=origin_candle.low,
                creation_index=origin_candle.index,
                creation_time=origin_candle.timestamp,
            ))

        return order_blocks

    @staticmethod
    def _find_origin_candle(candles: list[Candle], bos: BOSEvent) -> Candle | None:
        """
        Remonte depuis la bougie de cassure jusqu'à trouver la dernière
        bougie de sens opposé au mouvement impulsif : c'est l'Order Block.
        """
        relevant = [c for c in candles if c.index <= bos.candle_index]
        relevant.sort(key=lambda c: c.index, reverse=True)

        for candle in relevant:
            if bos.direction == TrendDirection.BULLISH and candle.is_bearish:
                return candle
            if bos.direction == TrendDirection.BEARISH and candle.is_bullish:
                return candle
        return None

    def update_status(self, order_blocks: list[OrderBlock], candles: list[Candle]) -> list[OrderBlock]:
        """
        Parcourt les bougies après la création de chaque OB pour déterminer
        s'il a été retesté (MITIGATED) ou totalement traversé (INVALIDATED).
        """
        for ob in order_blocks:
            for candle in candles:
                if candle.index <= ob.creation_index:
                    continue

                if ob.direction == TrendDirection.BULLISH:
                    fully_broken = candle.close < ob.zone_low
                    retested = ob.zone_low <= candle.low <= ob.zone_high
                else:
                    fully_broken = candle.close > ob.zone_high
                    retested = ob.zone_low <= candle.high <= ob.zone_high

                if fully_broken:
                    ob.status = OrderBlockStatus.INVALIDATED
                    break
                if retested and ob.status == OrderBlockStatus.UNMITIGATED:
                    ob.status = OrderBlockStatus.MITIGATED

        return order_blocks

    def unmitigated_blocks(self, order_blocks: list[OrderBlock]) -> list[OrderBlock]:
        return [ob for ob in order_blocks if ob.status == OrderBlockStatus.UNMITIGATED]
