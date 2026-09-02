"""
apps/analytics/services/analytics_service.py

Calcule les métriques de performance à partir du journal de trading réel
(apps.journal.models.TradeJournalEntry) :
  - Win Rate
  - Profit Factor
  - Drawdown (maximum, sur la courbe d'équité cumulée des trades clôturés)
  - Total Signals / Wins / Losses
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.journal.models import TradeJournalEntry, TradeResult


@dataclass
class AnalyticsSummary:
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_breakeven: int = 0
    win_rate: float = 0.0
    profit_factor: float | None = None
    max_drawdown: float = 0.0
    net_pnl: float = 0.0
    equity_curve: list[float] = field(default_factory=list)


class AnalyticsService:
    def compute_summary(self, user) -> AnalyticsSummary:
        closed_entries = (
            TradeJournalEntry.objects
            .filter(user=user)
            .exclude(result=TradeResult.OPEN)
            .order_by("closed_at", "opened_at")
        )

        summary = AnalyticsSummary()
        gross_profit = 0.0
        gross_loss = 0.0
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0

        for entry in closed_entries:
            summary.total_trades += 1
            pnl = entry.pnl or 0.0
            summary.net_pnl += pnl

            if entry.result == TradeResult.WIN:
                summary.total_wins += 1
                gross_profit += max(pnl, 0.0)
            elif entry.result == TradeResult.LOSS:
                summary.total_losses += 1
                gross_loss += abs(min(pnl, 0.0))
            else:
                summary.total_breakeven += 1

            equity += pnl
            summary.equity_curve.append(round(equity, 2))
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)

        if summary.total_trades:
            summary.win_rate = round(summary.total_wins / summary.total_trades * 100, 1)

        if gross_loss > 0:
            summary.profit_factor = round(gross_profit / gross_loss, 2)
        elif gross_profit > 0:
            summary.profit_factor = None  # aucune perte -> profit factor non défini (infini)

        summary.max_drawdown = round(max_drawdown, 2)
        summary.net_pnl = round(summary.net_pnl, 2)

        return summary

    def signals_summary(self, user=None) -> dict:
        """Statistiques côté signaux générés (indépendant du journal exécuté)."""
        from apps.signals.models import SignalRecord

        queryset = SignalRecord.objects.all()
        return {
            "total_signals": queryset.count(),
            "buy_signals": queryset.filter(direction="BUY").count(),
            "sell_signals": queryset.filter(direction="SELL").count(),
            "no_trade_signals": queryset.filter(direction="NO_TRADE").count(),
        }
