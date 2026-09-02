"""
apps/smc/services/sweep_engine.py

LIQUIDITY SWEEP ENGINE
-----------------------
Détecte quand le prix va chercher une zone de liquidité (mèche au-delà
du niveau) puis classe le sweep :
  - VALID_SWEEP : la mèche dépasse la zone MAIS la bougie clôture
    de nouveau du bon côté (à l'intérieur) => manipulation / chasse
    aux stops típique SMC, souvent suivi d'un retournement.
  - FALSE_SWEEP : la bougie clôture AU-DELÀ de la zone => ce n'est pas
    un sweep, c'est une vraie cassure (breakout), pas une manipulation.
"""

from __future__ import annotations

from apps.smc.services.dtos import Candle, LiquidityZone, SweepEvent, SweepValidity


class LiquiditySweepEngine:
    def detect(self, candles: list[Candle], zones: list[LiquidityZone]) -> list[SweepEvent]:
        events: list[SweepEvent] = []
        swept_zone_prices: set[float] = set()

        for zone in zones:
            for candle in candles:
                if zone.price in swept_zone_prices:
                    break

                if zone.kind == "BUY_SIDE":
                    # la mèche haute dépasse la zone
                    if candle.high > zone.price:
                        validity = (
                            SweepValidity.VALID
                            if candle.close < zone.price
                            else SweepValidity.FALSE
                        )
                        events.append(SweepEvent(
                            zone=zone,
                            sweep_candle_index=candle.index,
                            timestamp=candle.timestamp,
                            wick_price=candle.high,
                            close_price=candle.close,
                            validity=validity,
                        ))
                        swept_zone_prices.add(zone.price)

                elif zone.kind == "SELL_SIDE":
                    # la mèche basse dépasse la zone
                    if candle.low < zone.price:
                        validity = (
                            SweepValidity.VALID
                            if candle.close > zone.price
                            else SweepValidity.FALSE
                        )
                        events.append(SweepEvent(
                            zone=zone,
                            sweep_candle_index=candle.index,
                            timestamp=candle.timestamp,
                            wick_price=candle.low,
                            close_price=candle.close,
                            validity=validity,
                        ))
                        swept_zone_prices.add(zone.price)

        events.sort(key=lambda e: e.sweep_candle_index)
        return events

    def has_valid_sweep(self, events: list[SweepEvent]) -> bool:
        return any(e.validity == SweepValidity.VALID for e in events)

    def latest_valid_sweep(self, events: list[SweepEvent]) -> SweepEvent | None:
        valid = [e for e in events if e.validity == SweepValidity.VALID]
        return valid[-1] if valid else None
