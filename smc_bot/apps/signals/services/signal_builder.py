"""
apps/signals/services/signal_builder.py

SIGNAL BUILDER
--------------
Une fois qu'un scénario a validé une direction (BUY/SELL), ce module
calcule les niveaux concrets du signal :
  - Entry  : prix courant
  - Stop Loss : au-delà de la zone de structure/liquidité invalidante
  - Take Profit : basé sur le Risk Reward minimum (1:2 par défaut)
  - Confidence Score : score 0-100 basé sur le nombre de confluences
"""

from __future__ import annotations

from datetime import datetime

from apps.signals.services.dtos import MarketContext, Signal, TimeframeAnalysis
from apps.smc.services.dtos import Direction, OrderBlockStatus, SweepValidity, TrendDirection

# Buffer de sécurité appliqué au-delà du niveau de structure pour placer le SL
# (évite de se faire sortir par un simple bruit de marché juste sur le niveau).
STOP_LOSS_BUFFER_RATIO = 0.001  # 0.1% du prix


class SignalBuilder:
    def __init__(self, min_risk_reward: float = 2.0):
        self.min_risk_reward = min_risk_reward

    # ------------------------------------------------------------------
    def build(
        self,
        context: MarketContext,
        direction: Direction,
        scenario: str,
        base_reasons: list[str],
    ) -> Signal:
        if direction == Direction.NO_TRADE:
            return self._no_trade_signal(context, base_reasons, scenario)

        entry = context.current_price
        stop_loss = self._compute_stop_loss(context, direction)
        take_profit = self._compute_take_profit(entry, stop_loss, direction)
        risk_reward = self._compute_risk_reward(entry, stop_loss, take_profit)
        confidence = self._compute_confidence(context, direction, scenario)

        return Signal(
            instrument=context.instrument,
            direction=direction,
            entry=round(entry, 5),
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            risk_reward=round(risk_reward, 2),
            confidence_score=confidence,
            reasons=base_reasons,
            scenario=scenario,
            timestamp=context.current_time,
        )

    # ------------------------------------------------------------------
    def _no_trade_signal(self, context: MarketContext, reasons: list[str], scenario: str | None) -> Signal:
        return Signal(
            instrument=context.instrument,
            direction=Direction.NO_TRADE,
            entry=None,
            stop_loss=None,
            take_profit=None,
            risk_reward=None,
            confidence_score=0,
            reasons=reasons,
            scenario=scenario,
            timestamp=context.current_time,
        )

    # ------------------------------------------------------------------
    def _compute_stop_loss(self, context: MarketContext, direction: Direction) -> float:
        """
        Priorité : Order Block non-mitigé le plus proche, sinon dernier
        swing structurel, sinon fallback en % du prix.
        """
        m15 = context.m15
        price = context.current_price

        if direction == Direction.BUY:
            candidate_lows = [
                ob.zone_low for ob in m15.order_blocks
                if ob.direction == TrendDirection.BULLISH and ob.status != OrderBlockStatus.INVALIDATED
            ]
            if not candidate_lows and m15.structure.last_swing_low:
                candidate_lows = [m15.structure.last_swing_low.price]
            base = min(candidate_lows) if candidate_lows else price * (1 - 0.005)
            return base * (1 - STOP_LOSS_BUFFER_RATIO)

        else:  # SELL
            candidate_highs = [
                ob.zone_high for ob in m15.order_blocks
                if ob.direction == TrendDirection.BEARISH and ob.status != OrderBlockStatus.INVALIDATED
            ]
            if not candidate_highs and m15.structure.last_swing_high:
                candidate_highs = [m15.structure.last_swing_high.price]
            base = max(candidate_highs) if candidate_highs else price * (1 + 0.005)
            return base * (1 + STOP_LOSS_BUFFER_RATIO)

    def _compute_take_profit(self, entry: float, stop_loss: float, direction: Direction) -> float:
        risk_distance = abs(entry - stop_loss)
        reward_distance = risk_distance * self.min_risk_reward
        if direction == Direction.BUY:
            return entry + reward_distance
        return entry - reward_distance

    def _compute_risk_reward(self, entry: float, stop_loss: float, take_profit: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        return reward / risk if risk else 0.0

    # ------------------------------------------------------------------
    def _compute_confidence(self, context: MarketContext, direction: Direction, scenario: str) -> int:
        """
        Score de base 50, +points par confluence retrouvée.
        Plafonné à 98 (on ne donne jamais 100% de certitude sur un marché).
        """
        score = 50
        m30, m15 = context.m30, context.m15
        expected_trend = TrendDirection.BULLISH if direction == Direction.BUY else TrendDirection.BEARISH

        if self._last_bos_matches(m30, expected_trend):
            score += 12
        if self._last_bos_matches(m15, expected_trend):
            score += 12
        if any(s.validity == SweepValidity.VALID for s in m15.sweep_events):
            score += 10
        if not m15.is_range:
            score += 6

        if scenario in ("SCENARIO_3", "SCENARIO_4"):
            last_choch = m15.choch_events[-1] if m15.choch_events else None
            if last_choch:
                score += round(last_choch.strength / 10)  # jusqu'à +10

        rsi = context.latest_rsi
        if rsi is not None:
            if direction == Direction.BUY and rsi.value <= 1:
                score += 10
            elif direction == Direction.BUY and rsi.value <= 10:
                score += 6
            elif direction == Direction.SELL and rsi.value >= 98:
                score += 10
            elif direction == Direction.SELL and rsi.value >= 90:
                score += 6

        return min(score, 98)

    @staticmethod
    def _last_bos_matches(analysis: TimeframeAnalysis, expected: TrendDirection) -> bool:
        if not analysis.bos_events:
            return False
        return analysis.bos_events[-1].direction == expected
