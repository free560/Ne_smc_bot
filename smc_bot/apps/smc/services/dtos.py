"""
apps/smc/services/dtos.py

Structures de données (DTO) partagées par tous les moteurs SMC.
Ces objets sont volontairement indépendants de Django (pas de models.py ici) :
en Phase 2, tout tourne en Python pur, testable hors framework.
L'intégration Django (persistance en base) arrive en Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# ENUMS
# --------------------------------------------------------------------------

class Timeframe(str, Enum):
    M1 = "M1"
    M15 = "M15"
    M30 = "M30"


class TrendDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"


class SwingType(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


class StructureLabel(str, Enum):
    HH = "HH"   # Higher High
    HL = "HL"   # Higher Low
    LH = "LH"   # Lower High
    LL = "LL"   # Lower Low


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class SweepValidity(str, Enum):
    VALID = "VALID_SWEEP"
    FALSE = "FALSE_SWEEP"


class OrderBlockStatus(str, Enum):
    UNMITIGATED = "UNMITIGATED"   # zone encore vierge, valide pour une entrée
    MITIGATED = "MITIGATED"       # le prix est repassé dedans, zone consommée
    INVALIDATED = "INVALIDATED"   # le prix a totalement traversé la zone


# --------------------------------------------------------------------------
# MARCHÉ
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Candle:
    """Une bougie OHLC. `index` = position dans la série (0 = plus ancienne)."""
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low


# --------------------------------------------------------------------------
# STRUCTURE DE MARCHÉ
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SwingPoint:
    """Un point pivot (haut ou bas) détecté sur la série de bougies."""
    candle_index: int
    timestamp: datetime
    price: float
    swing_type: SwingType
    label: Optional[StructureLabel] = None  # HH / HL / LH / LL une fois classifié


@dataclass
class StructureState:
    """Résultat complet de l'analyse de structure sur un timeframe donné."""
    timeframe: Timeframe
    swings: list[SwingPoint] = field(default_factory=list)
    trend: TrendDirection = TrendDirection.RANGE

    @property
    def last_swing_high(self) -> Optional[SwingPoint]:
        highs = [s for s in self.swings if s.swing_type == SwingType.HIGH]
        return highs[-1] if highs else None

    @property
    def last_swing_low(self) -> Optional[SwingPoint]:
        lows = [s for s in self.swings if s.swing_type == SwingType.LOW]
        return lows[-1] if lows else None

    @property
    def previous_swing_high(self) -> Optional[SwingPoint]:
        highs = [s for s in self.swings if s.swing_type == SwingType.HIGH]
        return highs[-2] if len(highs) >= 2 else None

    @property
    def previous_swing_low(self) -> Optional[SwingPoint]:
        lows = [s for s in self.swings if s.swing_type == SwingType.LOW]
        return lows[-2] if len(lows) >= 2 else None


# --------------------------------------------------------------------------
# BOS / CHOCH
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BOSEvent:
    """Break of Structure."""
    timeframe: Timeframe
    direction: TrendDirection      # BULLISH ou BEARISH (jamais RANGE)
    break_price: float
    broken_swing: SwingPoint
    candle_index: int
    timestamp: datetime


@dataclass(frozen=True)
class CHoCHEvent:
    """Change of Character."""
    timeframe: Timeframe
    direction: TrendDirection      # nouvelle direction après le CHoCH
    price: float
    candle_index: int
    timestamp: datetime
    strength: float                # 0-100, voir CHoCHEngine._compute_strength


# --------------------------------------------------------------------------
# LIQUIDITÉ
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LiquidityZone:
    kind: str                      # "BUY_SIDE" ou "SELL_SIDE"
    price: float
    source_swings: list[SwingPoint]
    is_equal_level: bool = False   # True si formé par des equal highs/lows


@dataclass(frozen=True)
class SweepEvent:
    zone: LiquidityZone
    sweep_candle_index: int
    timestamp: datetime
    wick_price: float
    close_price: float
    validity: SweepValidity


# --------------------------------------------------------------------------
# ORDER BLOCKS / FVG
# --------------------------------------------------------------------------

@dataclass
class OrderBlock:
    direction: TrendDirection      # BULLISH ou BEARISH
    zone_high: float
    zone_low: float
    creation_index: int
    creation_time: datetime
    status: OrderBlockStatus = OrderBlockStatus.UNMITIGATED

    @property
    def midpoint(self) -> float:
        return (self.zone_high + self.zone_low) / 2


@dataclass(frozen=True)
class FairValueGap:
    direction: TrendDirection      # BULLISH ou BEARISH
    gap_top: float
    gap_bottom: float
    creation_index: int
    creation_time: datetime

    @property
    def gap_size(self) -> float:
        return abs(self.gap_top - self.gap_bottom)
