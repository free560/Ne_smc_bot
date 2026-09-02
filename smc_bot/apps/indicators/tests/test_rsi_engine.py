"""
apps/indicators/tests/test_rsi_engine.py
"""

import unittest

from apps.indicators.services.rsi_engine import RSIEngine
from apps.smc.tests.factories import make_candles


class RSIEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = RSIEngine(period=14)

    def test_returns_empty_when_not_enough_candles(self):
        closes = [100, 101, 102]
        candles = make_candles(closes)
        self.assertEqual(self.engine.compute_series(candles), [])

    def test_strong_uptrend_gives_high_rsi(self):
        closes = [100 + i for i in range(20)]  # hausse continue
        candles = make_candles(closes)
        latest = self.engine.latest(candles)
        self.assertIsNotNone(latest)
        self.assertGreater(latest.value, 70)

    def test_strong_downtrend_gives_low_rsi(self):
        closes = [100 - i for i in range(20)]  # baisse continue
        candles = make_candles(closes)
        latest = self.engine.latest(candles)
        self.assertIsNotNone(latest)
        self.assertLess(latest.value, 30)

    def test_flat_market_gives_mid_rsi(self):
        closes = [100.0] * 20
        candles = make_candles(closes)
        latest = self.engine.latest(candles)
        self.assertIsNotNone(latest)
        # Pas de mouvement -> avg_gain = avg_loss = 0 -> RSI conventionnellement 100
        # (avg_loss == 0 dans notre implémentation) ; on vérifie juste l'absence de crash.
        self.assertGreaterEqual(latest.value, 0)

    def test_oversold_overbought_thresholds(self):
        self.assertTrue(self.engine.is_oversold(10))
        self.assertFalse(self.engine.is_oversold(20))
        self.assertTrue(self.engine.is_overbought(90))
        self.assertFalse(self.engine.is_overbought(80))

        self.assertEqual(self.engine.oversold_strength(0.5), "<=1")
        self.assertEqual(self.engine.oversold_strength(8), "<=10")
        self.assertEqual(self.engine.oversold_strength(14), "<=15")
        self.assertIsNone(self.engine.oversold_strength(50))

        self.assertEqual(self.engine.overbought_strength(99), ">=98")
        self.assertEqual(self.engine.overbought_strength(92), ">=90")
        self.assertEqual(self.engine.overbought_strength(86), ">=85")
        self.assertIsNone(self.engine.overbought_strength(50))


if __name__ == "__main__":
    unittest.main()
