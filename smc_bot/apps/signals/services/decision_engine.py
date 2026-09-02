"""
apps/signals/services/decision_engine.py

DECISION ENGINE
----------------
Point d'entrée unique du moteur de signaux. Implémente la hiérarchie de
décision du cahier des charges :

    Level 1 : M30 Structure        (BOS, CHoCH, Liquidité)
    Level 2 : M15 Confirmation     (BOS/CHoCH/Liquidité validés)
    Level 3 : Instrument Validation (BOOM1000 / CRASH1000)
    Level 4 : RSI Confirmation     (M1)
    Level 5 : Signal Generation    (BUY / SELL / NO TRADE)

Usage :
    engine = DecisionEngine()
    signal = engine.generate_signal(
        instrument="BOOM1000",
        m30_candles=..., m15_candles=..., m1_candles=...,
        current_time=...,
    )
"""

from __future__ import annotations

from datetime import datetime

from apps.indicators.services.rsi_engine import RSIEngine
from apps.signals.services.dtos import MarketContext, Signal, TimeframeAnalysis
from apps.signals.services.scenarios import ALL_SCENARIOS
from apps.smc.services.bos_engine import BOSEngine
from apps.smc.services.choch_engine import CHoCHEngine
from apps.smc.services.dtos import Candle, Direction, Timeframe
from apps.smc.services.fvg_engine import FairValueGapEngine
from apps.smc.services.liquidity_engine import LiquidityEngine
from apps.smc.services.market_structure import MarketStructureEngine
from apps.smc.services.order_block_engine import OrderBlockEngine
from apps.smc.services.range_filter import RangeFilter
from apps.smc.services.sweep_engine import LiquiditySweepEngine
from apps.signals.services.signal_builder import SignalBuilder

VALID_INSTRUMENTS = {"BOOM1000", "CRASH1000"}


class DecisionEngine:
    def __init__(
        self,
        structure_lookback: int = 2,
        rsi_period: int = 14,
        min_risk_reward: float = 2.0,
    ):
        self.structure_engine = MarketStructureEngine(lookback=structure_lookback)
        self.bos_engine = BOSEngine()
        self.choch_engine = CHoCHEngine()
        self.liquidity_engine = LiquidityEngine()
        self.sweep_engine = LiquiditySweepEngine()
        self.order_block_engine = OrderBlockEngine()
        self.fvg_engine = FairValueGapEngine()
        self.range_filter = RangeFilter()
        self.rsi_engine = RSIEngine(period=rsi_period)
        self.signal_builder = SignalBuilder(min_risk_reward=min_risk_reward)

    # ------------------------------------------------------------------
    # LEVEL 1 + LEVEL 2 : analyse SMC complète d'un timeframe
    # ------------------------------------------------------------------
    def _analyze_timeframe(self, candles: list[Candle], timeframe: Timeframe) -> TimeframeAnalysis:
        structure = self.structure_engine.analyze(candles, timeframe)
        bos_events = self.bos_engine.detect(candles, structure)
        choch_events = self.choch_engine.detect(candles, structure)
        liquidity_zones = self.liquidity_engine.identify_zones(structure)
        sweep_events = self.sweep_engine.detect(candles, liquidity_zones)
        order_blocks = self.order_block_engine.detect(candles, bos_events)
        order_blocks = self.order_block_engine.update_status(order_blocks, candles)
        fvgs = self.fvg_engine.detect(candles)
        is_range = self.range_filter.is_range(structure, bos_events)

        return TimeframeAnalysis(
            timeframe=timeframe,
            structure=structure,
            bos_events=bos_events,
            choch_events=choch_events,
            liquidity_zones=liquidity_zones,
            sweep_events=sweep_events,
            order_blocks=order_blocks,
            fair_value_gaps=fvgs,
            is_range=is_range,
        )

    # ------------------------------------------------------------------
    # PIPELINE COMPLET
    # ------------------------------------------------------------------
    def build_context(
        self,
        instrument: str,
        m30_candles: list[Candle],
        m15_candles: list[Candle],
        m1_candles: list[Candle],
        current_time: datetime | None = None,
    ) -> MarketContext:
        m30_analysis = self._analyze_timeframe(m30_candles, Timeframe.M30)
        m15_analysis = self._analyze_timeframe(m15_candles, Timeframe.M15)
        rsi_series = self.rsi_engine.compute_series(m1_candles)

        current_price = m1_candles[-1].close if m1_candles else 0.0
        resolved_time = current_time or (m1_candles[-1].timestamp if m1_candles else datetime.utcnow())

        return MarketContext(
            instrument=instrument,
            m30=m30_analysis,
            m15=m15_analysis,
            rsi_series=rsi_series,
            current_price=current_price,
            current_time=resolved_time,
        )

    # ------------------------------------------------------------------
    # LEVEL 3, 4, 5 : validation instrument + RSI + génération du signal
    # ------------------------------------------------------------------
    def generate_signal(
        self,
        instrument: str,
        m30_candles: list[Candle],
        m15_candles: list[Candle],
        m1_candles: list[Candle],
        current_time: datetime | None = None,
    ) -> Signal:
        # Level 3 : validation de l'instrument
        if instrument not in VALID_INSTRUMENTS:
            context = self.build_context(instrument, m30_candles, m15_candles, m1_candles, current_time)
            return self.signal_builder.build(
                context, Direction.NO_TRADE, "INVALID_INSTRUMENT",
                [f"Instrument non supporté : {instrument} (attendu BOOM1000 ou CRASH1000)"],
            )

        # Level 1 + Level 2 : structure M30/M15, BOS, CHoCH, liquidité
        context = self.build_context(instrument, m30_candles, m15_candles, m1_candles, current_time)

        # Range global -> NO TRADE immédiat (avant même d'essayer les scénarios)
        if context.m30.is_range or context.m15.is_range:
            return self.signal_builder.build(
                context, Direction.NO_TRADE, "RANGE_FILTER",
                ["Marché en range (structure faible ou absence de BOS récent) -> NO TRADE"],
            )

        # Level 4 + Level 5 : on essaie chaque scénario dans l'ordre
        for scenario_fn in ALL_SCENARIOS:
            result = scenario_fn(context, self.rsi_engine)
            if result is not None:
                direction, scenario_name, reasons = result
                return self.signal_builder.build(context, direction, scenario_name, reasons)

        # Aucun scénario validé
        reasons = ["Aucun scénario de la stratégie n'est validé sur ce contexte de marché"]
        rsi = context.latest_rsi
        if rsi is not None:
            reasons.append(f"RSI actuel : {rsi.value}")
        return self.signal_builder.build(context, Direction.NO_TRADE, None, reasons)
