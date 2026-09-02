"""
apps/risk/tests/test_engines.py
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.risk.models import AccountState, RiskSettings
from apps.risk.services.capital_protection_engine import CapitalProtectionEngine
from apps.risk.services.position_size_engine import PositionSizeEngine

User = get_user_model()


class PositionSizeEngineTests(TestCase):
    def setUp(self):
        self.engine = PositionSizeEngine(pip_value_per_lot=1.0)

    def test_calculates_lot_size(self):
        result = self.engine.calculate(balance=1000, risk_percent=1, entry=100, stop_loss=95)
        self.assertGreater(result.lot_size, 0)
        self.assertEqual(result.risk_amount, 10.0)
        self.assertEqual(result.stop_loss_distance, 5.0)
        self.assertIsNone(result.warning)

    def test_zero_balance_returns_zero_lot(self):
        result = self.engine.calculate(balance=0, risk_percent=1, entry=100, stop_loss=95)
        self.assertEqual(result.lot_size, 0.0)
        self.assertIsNotNone(result.warning)

    def test_zero_stop_distance_returns_zero_lot(self):
        result = self.engine.calculate(balance=1000, risk_percent=1, entry=100, stop_loss=100)
        self.assertEqual(result.lot_size, 0.0)
        self.assertIsNotNone(result.warning)

    def test_never_below_min_lot(self):
        result = self.engine.calculate(balance=10, risk_percent=0.1, entry=100, stop_loss=50)
        self.assertGreaterEqual(result.lot_size, self.engine.min_lot)


class CapitalProtectionEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="trader1", password="x")
        self.settings = RiskSettings.objects.create(user=self.user, max_consecutive_losses=3, max_daily_drawdown_percent=20.0)
        self.account = AccountState.objects.create(user=self.user, balance=900, day_start_balance=1000, consecutive_losses=0)
        self.engine = CapitalProtectionEngine()

    def test_no_halt_when_within_limits(self):
        result = self.engine.evaluate(self.account, self.settings)
        self.assertFalse(result.should_halt)

    def test_halts_on_consecutive_losses(self):
        self.account.consecutive_losses = 3
        result = self.engine.evaluate(self.account, self.settings)
        self.assertTrue(result.should_halt)
        self.assertIn("pertes consécutives", result.reason)

    def test_halts_on_daily_drawdown(self):
        self.account.balance = 750  # 25% de drawdown vs day_start_balance=1000
        result = self.engine.evaluate(self.account, self.settings)
        self.assertTrue(result.should_halt)
        self.assertIn("Drawdown", result.reason)

    def test_apply_persists_halted_state(self):
        self.account.consecutive_losses = 3
        self.engine.apply(self.account, self.settings)
        self.account.refresh_from_db()
        self.assertTrue(self.account.trading_halted)

    def test_register_trade_result_win_resets_streak(self):
        self.account.consecutive_losses = 2
        self.account.save()
        self.engine.register_trade_result(self.account, is_win=True, pnl=50)
        self.account.refresh_from_db()
        self.assertEqual(self.account.consecutive_losses, 0)
        self.assertEqual(self.account.balance, 950)

    def test_register_trade_result_loss_increments_streak(self):
        self.engine.register_trade_result(self.account, is_win=False, pnl=-30)
        self.account.refresh_from_db()
        self.assertEqual(self.account.consecutive_losses, 1)
        self.assertEqual(self.account.balance, 870)

    def test_reset_daily_counters(self):
        self.account.consecutive_losses = 3
        self.account.trading_halted = True
        self.account.save()
        self.engine.reset_daily_counters(self.account, date(2026, 8, 24))
        self.account.refresh_from_db()
        self.assertFalse(self.account.trading_halted)
        self.assertEqual(self.account.day_start_balance, self.account.balance)
