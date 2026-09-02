"""
apps/analytics/tests/test_analytics_service.py
"""

from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analytics.services.analytics_service import AnalyticsService
from apps.journal.models import TradeJournalEntry, TradeResult

User = get_user_model()


def _entry(user, result, pnl, i=0):
    return TradeJournalEntry.objects.create(
        user=user, instrument="BOOM1000", direction="BUY",
        entry=100, stop_loss=95, take_profit=110, result=result, pnl=pnl,
        opened_at=datetime(2026, 8, 1, 10, i, tzinfo=timezone.utc),
        closed_at=datetime(2026, 8, 1, 11, i, tzinfo=timezone.utc),
    )


class AnalyticsServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="negos", password="x")
        self.service = AnalyticsService()

    def test_empty_journal_returns_zeroed_summary(self):
        summary = self.service.compute_summary(self.user)
        self.assertEqual(summary.total_trades, 0)
        self.assertEqual(summary.win_rate, 0.0)
        self.assertIsNone(summary.profit_factor)

    def test_open_trades_are_excluded(self):
        TradeJournalEntry.objects.create(
            user=self.user, instrument="BOOM1000", direction="BUY",
            entry=100, stop_loss=95, take_profit=110, result=TradeResult.OPEN,
            opened_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        summary = self.service.compute_summary(self.user)
        self.assertEqual(summary.total_trades, 0)

    def test_win_rate_and_profit_factor(self):
        _entry(self.user, TradeResult.WIN, 100, i=0)
        _entry(self.user, TradeResult.WIN, 50, i=1)
        _entry(self.user, TradeResult.LOSS, -60, i=2)

        summary = self.service.compute_summary(self.user)
        self.assertEqual(summary.total_trades, 3)
        self.assertEqual(summary.total_wins, 2)
        self.assertEqual(summary.total_losses, 1)
        self.assertAlmostEqual(summary.win_rate, 66.7, places=1)
        self.assertAlmostEqual(summary.profit_factor, 150 / 60, places=2)
        self.assertEqual(summary.net_pnl, 90)

    def test_equity_curve_and_drawdown(self):
        _entry(self.user, TradeResult.WIN, 100, i=0)   # équité: 100 (peak)
        _entry(self.user, TradeResult.LOSS, -40, i=1)  # équité: 60 (drawdown 40)
        _entry(self.user, TradeResult.WIN, 20, i=2)    # équité: 80

        summary = self.service.compute_summary(self.user)
        self.assertEqual(summary.equity_curve, [100, 60, 80])
        self.assertEqual(summary.max_drawdown, 40)

    def test_only_wins_gives_undefined_profit_factor(self):
        _entry(self.user, TradeResult.WIN, 100, i=0)
        summary = self.service.compute_summary(self.user)
        self.assertIsNone(summary.profit_factor)

    def test_signals_summary_counts_all_directions(self):
        from apps.signals.models import SignalRecord

        SignalRecord.objects.create(instrument="BOOM1000", direction="BUY", generated_at=datetime.now(timezone.utc))
        SignalRecord.objects.create(instrument="CRASH1000", direction="SELL", generated_at=datetime.now(timezone.utc))
        SignalRecord.objects.create(instrument="BOOM1000", direction="NO_TRADE", generated_at=datetime.now(timezone.utc))

        result = self.service.signals_summary()
        self.assertEqual(result["total_signals"], 3)
        self.assertEqual(result["buy_signals"], 1)
        self.assertEqual(result["sell_signals"], 1)
        self.assertEqual(result["no_trade_signals"], 1)
