"""
apps/signals/tests/test_scenarios.py

Teste directement la logique des 4 scénarios en construisant un
MarketContext à la main (plutôt que de dépendre de la détection fractale
sur des données OHLC synthétiques, plus fragile). Ça isole et garantit
la correction de la logique de décision elle-même.
"""

import unittest
from datetime import datetime

from apps.indicators.services.rsi_engine import RSIEngine, RSIValue
from apps.signals.services.dtos import MarketContext, TimeframeAnalysis
from apps.signals.services.scenarios import (
    ALL_SCENARIOS,
    scenario_1_boom_bullish,
    scenario_2_crash_bearish,
    scenario_3_crash_bullish_reversal,
    scenario_4_boom_bearish_reversal,
)
from apps.smc.services.dtos import (
    BOSEvent,
    CHoCHEvent,
    Direction,
    LiquidityZone,
    StructureState,
    SweepEvent,
    SweepValidity,
    SwingPoint,
    SwingType,
    Timeframe,
    TrendDirection,
)

NOW = datetime(2026, 8, 22, 10, 0)


def _swing(index, price, swing_type):
    return SwingPoint(candle_index=index, timestamp=NOW, price=price, swing_type=swing_type)


def _bos(direction, timeframe, index=10):
    return BOSEvent(
        timeframe=timeframe,
        direction=direction,
        break_price=100.0,
        broken_swing=_swing(index - 1, 99.0, SwingType.HIGH if direction == TrendDirection.BULLISH else SwingType.LOW),
        candle_index=index,
        timestamp=NOW,
    )


def _valid_sweep():
    zone = LiquidityZone(kind="SELL_SIDE", price=95.0, source_swings=[_swing(3, 95.0, SwingType.LOW)])
    return SweepEvent(
        zone=zone, sweep_candle_index=5, timestamp=NOW,
        wick_price=94.0, close_price=96.0, validity=SweepValidity.VALID,
    )


def _choch(direction, strength=80.0):
    return CHoCHEvent(timeframe=Timeframe.M15, direction=direction, price=100.0,
                       candle_index=6, timestamp=NOW, strength=strength)


def _make_context(
    instrument: str,
    m30_direction: TrendDirection | None,
    m15_direction: TrendDirection | None,
    with_valid_sweep: bool = True,
    m15_choch_direction: TrendDirection | None = None,
    rsi_value: float | None = None,
    m30_range: bool = False,
    m15_range: bool = False,
) -> MarketContext:
    m30_structure = StructureState(timeframe=Timeframe.M30, swings=[], trend=m30_direction or TrendDirection.RANGE)
    m15_structure = StructureState(timeframe=Timeframe.M15, swings=[], trend=m15_direction or TrendDirection.RANGE)

    m30 = TimeframeAnalysis(
        timeframe=Timeframe.M30, structure=m30_structure,
        bos_events=[_bos(m30_direction, Timeframe.M30)] if m30_direction else [],
        is_range=m30_range,
    )
    m15 = TimeframeAnalysis(
        timeframe=Timeframe.M15, structure=m15_structure,
        bos_events=[_bos(m15_direction, Timeframe.M15)] if m15_direction else [],
        choch_events=[_choch(m15_choch_direction)] if m15_choch_direction else [],
        sweep_events=[_valid_sweep()] if with_valid_sweep else [],
        is_range=m15_range,
    )

    rsi_series = [RSIValue(candle_index=20, value=rsi_value)] if rsi_value is not None else []

    return MarketContext(
        instrument=instrument, m30=m30, m15=m15, rsi_series=rsi_series,
        current_price=100.0, current_time=NOW,
    )


class Scenario1Tests(unittest.TestCase):
    def setUp(self):
        self.rsi_engine = RSIEngine(period=14)

    def test_fires_on_full_bullish_setup_with_oversold_rsi(self):
        ctx = _make_context(
            "BOOM1000", TrendDirection.BULLISH, TrendDirection.BULLISH,
            with_valid_sweep=True, rsi_value=8.0,
        )
        result = scenario_1_boom_bullish(ctx, self.rsi_engine)
        self.assertIsNotNone(result)
        direction, name, reasons = result
        self.assertEqual(direction, Direction.BUY)
        self.assertEqual(name, "SCENARIO_1")
        self.assertTrue(len(reasons) >= 4)

    def test_does_not_fire_wrong_instrument(self):
        ctx = _make_context("CRASH1000", TrendDirection.BULLISH, TrendDirection.BULLISH, rsi_value=8.0)
        self.assertIsNone(scenario_1_boom_bullish(ctx, self.rsi_engine))

    def test_does_not_fire_without_rsi_oversold(self):
        ctx = _make_context("BOOM1000", TrendDirection.BULLISH, TrendDirection.BULLISH, rsi_value=50.0)
        self.assertIsNone(scenario_1_boom_bullish(ctx, self.rsi_engine))

    def test_does_not_fire_without_liquidity_sweep(self):
        ctx = _make_context("BOOM1000", TrendDirection.BULLISH, TrendDirection.BULLISH,
                             with_valid_sweep=False, rsi_value=8.0)
        self.assertIsNone(scenario_1_boom_bullish(ctx, self.rsi_engine))

    def test_does_not_fire_in_range(self):
        ctx = _make_context("BOOM1000", TrendDirection.BULLISH, TrendDirection.BULLISH,
                             rsi_value=8.0, m15_range=True)
        self.assertIsNone(scenario_1_boom_bullish(ctx, self.rsi_engine))


class Scenario2Tests(unittest.TestCase):
    def setUp(self):
        self.rsi_engine = RSIEngine(period=14)

    def test_fires_on_full_bearish_setup_with_overbought_rsi(self):
        ctx = _make_context(
            "CRASH1000", TrendDirection.BEARISH, TrendDirection.BEARISH,
            with_valid_sweep=True, rsi_value=93.0,
        )
        result = scenario_2_crash_bearish(ctx, self.rsi_engine)
        self.assertIsNotNone(result)
        direction, name, _ = result
        self.assertEqual(direction, Direction.SELL)
        self.assertEqual(name, "SCENARIO_2")


class Scenario3And4Tests(unittest.TestCase):
    def setUp(self):
        self.rsi_engine = RSIEngine(period=14)

    def test_scenario_3_crash_bullish_reversal_no_rsi_needed(self):
        ctx = _make_context(
            "CRASH1000", None, TrendDirection.BULLISH,
            with_valid_sweep=True, m15_choch_direction=TrendDirection.BULLISH,
            rsi_value=None,
        )
        result = scenario_3_crash_bullish_reversal(ctx, self.rsi_engine)
        self.assertIsNotNone(result)
        direction, name, _ = result
        self.assertEqual(direction, Direction.BUY)
        self.assertEqual(name, "SCENARIO_3")

    def test_scenario_4_boom_bearish_reversal_no_rsi_needed(self):
        ctx = _make_context(
            "BOOM1000", None, TrendDirection.BEARISH,
            with_valid_sweep=True, m15_choch_direction=TrendDirection.BEARISH,
            rsi_value=None,
        )
        result = scenario_4_boom_bearish_reversal(ctx, self.rsi_engine)
        self.assertIsNotNone(result)
        direction, name, _ = result
        self.assertEqual(direction, Direction.SELL)
        self.assertEqual(name, "SCENARIO_4")

    def test_scenario_3_requires_choch_not_just_bos(self):
        ctx = _make_context("CRASH1000", None, TrendDirection.BULLISH, with_valid_sweep=True)
        self.assertIsNone(scenario_3_crash_bullish_reversal(ctx, self.rsi_engine))


class ScenarioPriorityTests(unittest.TestCase):
    """Vérifie que le premier scénario valide dans l'ordre est bien celui retenu."""

    def test_scenario_1_takes_priority_when_multiple_could_apply(self):
        rsi_engine = RSIEngine(period=14)
        ctx = _make_context(
            "BOOM1000", TrendDirection.BULLISH, TrendDirection.BULLISH,
            with_valid_sweep=True, rsi_value=5.0,
        )
        for scenario_fn in ALL_SCENARIOS:
            result = scenario_fn(ctx, rsi_engine)
            if result is not None:
                self.assertEqual(result[1], "SCENARIO_1")
                break
        else:
            self.fail("Aucun scénario n'a été déclenché")


if __name__ == "__main__":
    unittest.main()
