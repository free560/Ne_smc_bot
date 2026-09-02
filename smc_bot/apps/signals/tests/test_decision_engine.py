"""
apps/signals/tests/test_decision_engine.py

Test d'intégration : vérifie que le DecisionEngine orchestre correctement
tous les moteurs SMC + RSI et produit un Signal cohérent, dans deux cas :
  1. Marché plat -> NO TRADE (filtré par le RangeFilter)
  2. Instrument invalide -> NO TRADE immédiat
"""

import unittest

from apps.signals.services.decision_engine import DecisionEngine
from apps.smc.services.dtos import Direction
from apps.smc.tests.factories import make_candles


class DecisionEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_flat_market_returns_no_trade(self):
        flat_closes = [100 + (0.05 if i % 2 == 0 else -0.05) for i in range(30)]
        m30 = make_candles(flat_closes)
        m15 = make_candles(flat_closes)
        m1 = make_candles(flat_closes)

        signal = self.engine.generate_signal("BOOM1000", m30, m15, m1)

        self.assertEqual(signal.direction, Direction.NO_TRADE)
        self.assertIsNone(signal.entry)
        self.assertEqual(signal.confidence_score, 0)
        self.assertTrue(len(signal.reasons) > 0)

    def test_invalid_instrument_returns_no_trade(self):
        closes = [100 + i for i in range(30)]
        candles = make_candles(closes)

        signal = self.engine.generate_signal("VOLATILITY75", candles, candles, candles)

        self.assertEqual(signal.direction, Direction.NO_TRADE)
        self.assertEqual(signal.scenario, "INVALID_INSTRUMENT")

    def test_signal_to_dict_is_json_serializable(self):
        import json

        closes = [100 + (0.05 if i % 2 == 0 else -0.05) for i in range(30)]
        candles = make_candles(closes)
        signal = self.engine.generate_signal("CRASH1000", candles, candles, candles)

        # Ne doit jamais lever d'exception, même pour un NO_TRADE
        payload = json.dumps(signal.to_dict())
        self.assertIn("CRASH1000", payload)

    def test_build_context_exposes_latest_rsi(self):
        closes = [100 + i for i in range(30)]
        candles = make_candles(closes)
        context = self.engine.build_context("BOOM1000", candles, candles, candles)

        self.assertIsNotNone(context.latest_rsi)
        self.assertEqual(context.instrument, "BOOM1000")


if __name__ == "__main__":
    unittest.main()
