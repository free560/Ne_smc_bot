"""
apps/signals/services/scenarios.py

Les 4 scénarios de la stratégie SMC RSI BOOM & CRASH 1000 PRO.
Chaque fonction reçoit le MarketContext complet et renvoie soit :
  - (Direction.BUY / Direction.SELL, "SCENARIO_X", [raisons...])
  - None  si les conditions du scénario ne sont pas remplies.

L'ordre d'évaluation (voir DecisionEngine) suit la hiérarchie de décision
du cahier des charges : structure M30 -> confirmation M15 ->
validation instrument -> RSI -> génération du signal.
"""

from __future__ import annotations

from apps.indicators.services.rsi_engine import RSIEngine
from apps.signals.services.dtos import MarketContext
from apps.smc.services.dtos import Direction, SweepValidity, TrendDirection

ScenarioResult = tuple[Direction, str, list[str]]

BOOM_INSTRUMENT = "BOOM1000"
CRASH_INSTRUMENT = "CRASH1000"


def _bos_direction_ok(context: MarketContext, expected: TrendDirection) -> bool:
    m30_ok = bool(context.m30.bos_events) and context.m30.bos_events[-1].direction == expected
    m15_ok = bool(context.m15.bos_events) and context.m15.bos_events[-1].direction == expected
    return m30_ok and m15_ok


def _liquidity_validated(context: MarketContext) -> bool:
    """Liquidité validée = au moins un sweep VALID sur M15 (chasse aux stops confirmée)."""
    return any(s.validity == SweepValidity.VALID for s in context.m15.sweep_events)


def _not_range(context: MarketContext) -> bool:
    return not context.m30.is_range and not context.m15.is_range


# --------------------------------------------------------------------------
# SCÉNARIO 1 - BOOM 1000 BULLISH
# --------------------------------------------------------------------------
def scenario_1_boom_bullish(context: MarketContext, rsi_engine: RSIEngine) -> ScenarioResult | None:
    if context.instrument != BOOM_INSTRUMENT:
        return None
    if not _bos_direction_ok(context, TrendDirection.BULLISH):
        return None
    if not _liquidity_validated(context):
        return None
    if not _not_range(context):
        return None

    rsi = context.latest_rsi
    if rsi is None or not rsi_engine.is_oversold(rsi.value, threshold=15.0):
        return None

    tier = rsi_engine.oversold_strength(rsi.value)
    reasons = [
        "BOS haussier confirmé sur M30",
        "BOS haussier confirmé sur M15",
        "Sweep de liquidité validé",
        "Marché en tendance (hors range)",
        f"RSI en survente ({rsi.value}, palier {tier})",
    ]
    return Direction.BUY, "SCENARIO_1", reasons


# --------------------------------------------------------------------------
# SCÉNARIO 2 - CRASH 1000 BEARISH
# --------------------------------------------------------------------------
def scenario_2_crash_bearish(context: MarketContext, rsi_engine: RSIEngine) -> ScenarioResult | None:
    if context.instrument != CRASH_INSTRUMENT:
        return None
    if not _bos_direction_ok(context, TrendDirection.BEARISH):
        return None
    if not _liquidity_validated(context):
        return None
    if not _not_range(context):
        return None

    rsi = context.latest_rsi
    if rsi is None or not rsi_engine.is_overbought(rsi.value, threshold=85.0):
        return None

    tier = rsi_engine.overbought_strength(rsi.value)
    reasons = [
        "BOS baissier confirmé sur M30",
        "BOS baissier confirmé sur M15",
        "Sweep de liquidité validé",
        "Marché en tendance (hors range)",
        f"RSI en surachat ({rsi.value}, palier {tier})",
    ]
    return Direction.SELL, "SCENARIO_2", reasons


# --------------------------------------------------------------------------
# SCÉNARIO 3 - CRASH 1000 BULLISH REVERSAL (pas de RSI requis)
# --------------------------------------------------------------------------
def scenario_3_crash_bullish_reversal(context: MarketContext, rsi_engine: RSIEngine) -> ScenarioResult | None:
    if context.instrument != CRASH_INSTRUMENT:
        return None

    m15_bullish_bos = bool(context.m15.bos_events) and context.m15.bos_events[-1].direction == TrendDirection.BULLISH
    m15_bullish_choch = bool(context.m15.choch_events) and context.m15.choch_events[-1].direction == TrendDirection.BULLISH

    if not (m15_bullish_bos and m15_bullish_choch):
        return None
    if not _liquidity_validated(context):
        return None
    if not _not_range(context):
        return None

    reasons = [
        "BOS haussier détecté (retournement)",
        "CHoCH haussier confirmé",
        "Sweep de liquidité validé",
        "Marché en tendance (hors range)",
        "Aucune confirmation RSI requise pour ce scénario",
    ]
    return Direction.BUY, "SCENARIO_3", reasons


# --------------------------------------------------------------------------
# SCÉNARIO 4 - BOOM 1000 BEARISH REVERSAL (pas de RSI requis)
# --------------------------------------------------------------------------
def scenario_4_boom_bearish_reversal(context: MarketContext, rsi_engine: RSIEngine) -> ScenarioResult | None:
    if context.instrument != BOOM_INSTRUMENT:
        return None

    m15_bearish_bos = bool(context.m15.bos_events) and context.m15.bos_events[-1].direction == TrendDirection.BEARISH
    m15_bearish_choch = bool(context.m15.choch_events) and context.m15.choch_events[-1].direction == TrendDirection.BEARISH

    if not (m15_bearish_bos and m15_bearish_choch):
        return None
    if not _liquidity_validated(context):
        return None
    if not _not_range(context):
        return None

    reasons = [
        "BOS baissier détecté (retournement)",
        "CHoCH baissier confirmé",
        "Sweep de liquidité validé",
        "Marché en tendance (hors range)",
        "Aucune confirmation RSI requise pour ce scénario",
    ]
    return Direction.SELL, "SCENARIO_4", reasons


# Ordre d'évaluation : scénarios "impulsion + RSI extrême" d'abord,
# puis scénarios de retournement (CHoCH) en second recours.
ALL_SCENARIOS = [
    scenario_1_boom_bullish,
    scenario_2_crash_bearish,
    scenario_3_crash_bullish_reversal,
    scenario_4_boom_bearish_reversal,
]
