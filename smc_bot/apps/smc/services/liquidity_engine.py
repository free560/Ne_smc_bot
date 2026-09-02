"""
apps/smc/services/liquidity_engine.py

LIQUIDITY ENGINE
----------------
Identifie les zones de liquidité :
  - Buy Side Liquidity  : au-dessus des swing highs (stops des vendeurs / breakout buyers)
  - Sell Side Liquidity : en dessous des swing lows (stops des acheteurs / breakout sellers)
  - Equal Highs / Equal Lows : plusieurs swings au même niveau (tolérance en %)
    => zone de liquidité renforcée, cible privilégiée d'un sweep.
"""

from __future__ import annotations

from apps.smc.services.dtos import LiquidityZone, StructureState, SwingPoint, SwingType


class LiquidityEngine:
    def __init__(self, equal_level_tolerance_pct: float = 0.05):
        """
        equal_level_tolerance_pct : tolérance (en %) pour considérer deux
        swings comme "equal highs/lows" (par défaut 0.05% du prix).
        """
        self.tolerance_pct = equal_level_tolerance_pct

    # ------------------------------------------------------------------
    def find_equal_levels(self, swings: list[SwingPoint], swing_type: SwingType) -> list[list[SwingPoint]]:
        """Regroupe les swings du même type dont les prix sont quasi identiques."""
        candidates = sorted(
            (s for s in swings if s.swing_type == swing_type),
            key=lambda s: s.price,
        )
        groups: list[list[SwingPoint]] = []
        current_group: list[SwingPoint] = []

        for swing in candidates:
            if not current_group:
                current_group = [swing]
                continue
            ref_price = current_group[0].price
            tolerance = ref_price * (self.tolerance_pct / 100)
            if abs(swing.price - ref_price) <= tolerance:
                current_group.append(swing)
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [swing]

        if len(current_group) >= 2:
            groups.append(current_group)

        return groups

    # ------------------------------------------------------------------
    def identify_zones(self, structure: StructureState) -> list[LiquidityZone]:
        zones: list[LiquidityZone] = []

        equal_highs = self.find_equal_levels(structure.swings, SwingType.HIGH)
        equal_lows = self.find_equal_levels(structure.swings, SwingType.LOW)

        for group in equal_highs:
            avg_price = sum(s.price for s in group) / len(group)
            zones.append(LiquidityZone(
                kind="BUY_SIDE",
                price=avg_price,
                source_swings=group,
                is_equal_level=True,
            ))

        for group in equal_lows:
            avg_price = sum(s.price for s in group) / len(group)
            zones.append(LiquidityZone(
                kind="SELL_SIDE",
                price=avg_price,
                source_swings=group,
                is_equal_level=True,
            ))

        # Chaque swing high isolé reste une zone de buy-side liquidity "simple"
        # (les stops au-dessus), idem pour les swing lows -> sell-side.
        grouped_indices = {s.candle_index for group in equal_highs + equal_lows for s in group}
        for swing in structure.swings:
            if swing.candle_index in grouped_indices:
                continue
            kind = "BUY_SIDE" if swing.swing_type == SwingType.HIGH else "SELL_SIDE"
            zones.append(LiquidityZone(
                kind=kind,
                price=swing.price,
                source_swings=[swing],
                is_equal_level=False,
            ))

        zones.sort(key=lambda z: z.price)
        return zones

    def buy_side_zones(self, zones: list[LiquidityZone]) -> list[LiquidityZone]:
        return [z for z in zones if z.kind == "BUY_SIDE"]

    def sell_side_zones(self, zones: list[LiquidityZone]) -> list[LiquidityZone]:
        return [z for z in zones if z.kind == "SELL_SIDE"]
