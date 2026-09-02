"""
apps/signals/services/dtos.py

Structures de données du moteur de signaux :
  - MarketContext : rassemble l'analyse complète (structure, BOS, CHoCH,
    liquidité, sweeps, order blocks, FVG, RSI) sur les 3 timeframes.
  - Signal : le résultat final (BUY / SELL / NO TRADE) prêt à afficher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from apps.indicators.services.rsi_engine import RSIValue
from apps.smc.services.dtos import (
    BOSEvent,
    CHoCHEvent,
    Direction,
    FairValueGap,
    LiquidityZone,
    OrderBlock,
    StructureState,
    SweepEvent,
    Timeframe,
)


@dataclass
class TimeframeAnalysis:
    """Résultat complet de l'analyse SMC pour un seul timeframe."""
    timeframe: Timeframe
    structure: StructureState
    bos_events: list[BOSEvent] = field(default_factory=list)
    choch_events: list[CHoCHEvent] = field(default_factory=list)
    liquidity_zones: list[LiquidityZone] = field(default_factory=list)
    sweep_events: list[SweepEvent] = field(default_factory=list)
    order_blocks: list[OrderBlock] = field(default_factory=list)
    fair_value_gaps: list[FairValueGap] = field(default_factory=list)
    is_range: bool = False


@dataclass
class MarketContext:
    """Contexte complet transmis au DecisionEngine pour un instrument donné."""
    instrument: str                     # "BOOM1000" ou "CRASH1000"
    m30: TimeframeAnalysis
    m15: TimeframeAnalysis
    rsi_series: list[RSIValue]
    current_price: float
    current_time: datetime

    @property
    def latest_rsi(self) -> RSIValue | None:
        return self.rsi_series[-1] if self.rsi_series else None


@dataclass
class Signal:
    """Signal final généré par le DecisionEngine, prêt pour l'affichage."""
    instrument: str
    direction: Direction
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward: float | None
    confidence_score: int
    reasons: list[str]
    scenario: str | None
    timestamp: datetime

    @property
    def is_tradeable(self) -> bool:
        return self.direction != Direction.NO_TRADE

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "direction": self.direction.value,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "confidence_score": self.confidence_score,
            "reasons": self.reasons,
            "scenario": self.scenario,
            "timestamp": self.timestamp.isoformat(),
        }
