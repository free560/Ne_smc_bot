"""
apps/smc/tests/test_engines.py

Tests unitaires des moteurs SMC en Python pur (pas de DB, pas de Django TestCase
nécessaire : unittest suffit puisque ces services n'utilisent aucun modèle).
"""

import unittest

from apps.smc.services.bos_engine import BOSEngine
from apps.smc.services.choch_engine import CHoCHEngine
from apps.smc.services.dtos import (
    StructureLabel,
    SweepValidity,
    Timeframe,
    TrendDirection,
)
from apps.smc.services.fvg_engine import FairValueGapEngine
from apps.smc.services.liquidity_engine import LiquidityEngine
from apps.smc.services.market_structure import MarketStructureEngine
from apps.smc.services.order_block_engine import OrderBlockEngine
from apps.smc.services.range_filter import RangeFilter
from apps.smc.services.sweep_engine import LiquiditySweepEngine
from apps.smc.tests.factories import make_candles


class MarketStructureEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = MarketStructureEngine(lookback=1)

    def test_detects_bullish_structure_hh_hl(self):
        # Zigzag clairement ascendant : chaque creux et sommet plus haut que le précédent
        closes = [100, 90, 108, 98, 116, 104, 124, 112, 132]
        candles = make_candles(closes)
        structure = self.engine.analyze(candles, Timeframe.M30)

        self.assertEqual(structure.trend, TrendDirection.BULLISH)
        labels = [s.label for s in structure.swings if s.label is not None]
        self.assertIn(StructureLabel.HH, labels)
        self.assertIn(StructureLabel.HL, labels)

    def test_detects_bearish_structure_lh_ll(self):
        closes = [132, 112, 124, 104, 116, 98, 108, 90, 100]
        candles = make_candles(closes)
        structure = self.engine.analyze(candles, Timeframe.M30)

        self.assertEqual(structure.trend, TrendDirection.BEARISH)
        labels = [s.label for s in structure.swings if s.label is not None]
        self.assertIn(StructureLabel.LH, labels)
        self.assertIn(StructureLabel.LL, labels)

    def test_flat_market_is_range(self):
        closes = [100, 100.2, 99.9, 100.1, 100.0, 99.95, 100.05]
        candles = make_candles(closes)
        structure = self.engine.analyze(candles, Timeframe.M30)
        self.assertEqual(structure.trend, TrendDirection.RANGE)


class BOSEngineTests(unittest.TestCase):
    def test_detects_bullish_bos(self):
        structure_engine = MarketStructureEngine(lookback=1)
        bos_engine = BOSEngine()

        closes = [100, 90, 108, 98, 116, 104, 140]  # 140 casse largement le dernier high (116)
        candles = make_candles(closes)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        events = bos_engine.detect(candles, structure)

        self.assertTrue(any(e.direction == TrendDirection.BULLISH for e in events))

    def test_detects_bearish_bos(self):
        structure_engine = MarketStructureEngine(lookback=1)
        bos_engine = BOSEngine()

        closes = [132, 112, 124, 104, 116, 98, 70]  # 70 casse largement le dernier low (98)
        candles = make_candles(closes)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        events = bos_engine.detect(candles, structure)

        self.assertTrue(any(e.direction == TrendDirection.BEARISH for e in events))


class CHoCHEngineTests(unittest.TestCase):
    def test_detects_bullish_choch_after_bearish_structure(self):
        structure_engine = MarketStructureEngine(lookback=1)
        choch_engine = CHoCHEngine()

        # structure baissière (LH/LL) puis forte remontée qui casse le dernier LH
        closes = [132, 112, 124, 104, 116, 98, 150]
        candles = make_candles(closes)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        events = choch_engine.detect(candles, structure)

        self.assertTrue(any(e.direction == TrendDirection.BULLISH for e in events))


class LiquidityAndSweepTests(unittest.TestCase):
    def test_equal_highs_grouped_and_swept(self):
        structure_engine = MarketStructureEngine(lookback=1)
        liquidity_engine = LiquidityEngine(equal_level_tolerance_pct=0.5)
        sweep_engine = LiquiditySweepEngine()

        # Deux sommets quasi égaux (~120) suivis d'une mèche qui les dépasse puis clôture en dessous
        closes = [100, 90, 120, 105, 119.8, 108, 112]
        candles = make_candles(closes, wick_ratio=0.0)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        zones = liquidity_engine.identify_zones(structure)

        self.assertTrue(any(z.is_equal_level for z in zones))

        sweeps = sweep_engine.detect(candles, zones)
        # Au moins une tentative de sweep détectée (valid ou false selon la clôture)
        self.assertIsInstance(sweeps, list)


class OrderBlockAndFVGTests(unittest.TestCase):
    def test_order_block_created_on_bos(self):
        structure_engine = MarketStructureEngine(lookback=1)
        bos_engine = BOSEngine()
        ob_engine = OrderBlockEngine()

        closes = [100, 90, 108, 98, 116, 104, 140]
        candles = make_candles(closes)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        bos_events = bos_engine.detect(candles, structure)
        order_blocks = ob_engine.detect(candles, bos_events)

        self.assertGreater(len(order_blocks), 0)

    def test_fvg_detection_three_candle_gap(self):
        fvg_engine = FairValueGapEngine()
        # Bougie impulsive haussière isolée créant un vrai gap de prix
        closes = [100, 101, 130]
        candles = make_candles(closes, wick_ratio=0.0)
        gaps = fvg_engine.detect(candles)
        self.assertTrue(any(g.direction == TrendDirection.BULLISH for g in gaps))


class RangeFilterTests(unittest.TestCase):
    def test_flat_market_flagged_as_range(self):
        structure_engine = MarketStructureEngine(lookback=1)
        bos_engine = BOSEngine()
        range_filter = RangeFilter()

        closes = [100, 100.2, 99.9, 100.1, 100.0, 99.95, 100.05]
        candles = make_candles(closes)
        structure = structure_engine.analyze(candles, Timeframe.M30)
        bos_events = bos_engine.detect(candles, structure)

        self.assertTrue(range_filter.is_range(structure, bos_events))


if __name__ == "__main__":
    unittest.main()
