"""
apps/smc/services/range_filter.py

RANGE FILTER
------------
Détermine si le marché est en TREND ou en RANGE.

Conditions de RANGE (au moins une suffit) :
  - Aucun BOS récent sur le timeframe de structure
  - Structure faible : trop peu de swings classifiés (HH/HL/LH/LL)
  - Marché latéral : les swing highs/lows oscillent dans une bande étroite

Si RANGE => le signal final doit être NO TRADE (voir DecisionEngine).
"""

from __future__ import annotations

from apps.smc.services.dtos import BOSEvent, StructureState, TrendDirection


class RangeFilter:
    def __init__(self, min_classified_swings: int = 3, sideways_ratio_threshold: float = 0.015):
        """
        min_classified_swings : nombre minimum de swings labellisés (HH/HL/LH/LL)
            requis pour considérer la structure comme "établie".
        sideways_ratio_threshold : si l'amplitude (max-min) des swings récents
            divisée par le prix moyen est inférieure à ce seuil, on considère
            le marché plat (par défaut 1.5%).
        """
        self.min_classified_swings = min_classified_swings
        self.sideways_ratio_threshold = sideways_ratio_threshold

    def is_range(self, structure: StructureState, bos_events: list[BOSEvent]) -> bool:
        # 1. Pas de BOS récent => pas de conviction directionnelle
        if not bos_events:
            return True

        # 2. Structure trop faible (pas assez de swings classifiés)
        classified = [s for s in structure.swings if s.label is not None]
        if len(classified) < self.min_classified_swings:
            return True

        # 3. Tendance déjà classifiée RANGE par le MarketStructureEngine
        if structure.trend == TrendDirection.RANGE:
            return True

        # 4. Marché plat : faible amplitude sur les derniers swings
        recent = structure.swings[-self.min_classified_swings:]
        prices = [s.price for s in recent]
        if prices:
            avg_price = sum(prices) / len(prices)
            amplitude_ratio = (max(prices) - min(prices)) / avg_price if avg_price else 0
            if amplitude_ratio < self.sideways_ratio_threshold:
                return True

        return False

    def classify(self, structure: StructureState, bos_events: list[BOSEvent]) -> str:
        return "RANGE" if self.is_range(structure, bos_events) else "TREND"
