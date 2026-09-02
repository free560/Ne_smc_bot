"""
apps/risk/services/capital_protection_engine.py

CAPITAL PROTECTION ENGINE
---------------------------
Décide si le trading doit être arrêté (STOP TRADING) selon :
  - 3 pertes consécutives (configurable)
  - Drawdown journalier > 20% (configurable)

Ce moteur ne fait que CALCULER l'état ; c'est au code appelant
(vues, tâches Celery) de persister `AccountState.trading_halted` et de
déclencher une notification.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.risk.models import AccountState, RiskSettings


@dataclass(frozen=True)
class ProtectionCheckResult:
    should_halt: bool
    reason: str | None = None


class CapitalProtectionEngine:
    def evaluate(self, account_state: AccountState, settings_: RiskSettings) -> ProtectionCheckResult:
        if account_state.consecutive_losses >= settings_.max_consecutive_losses:
            return ProtectionCheckResult(
                should_halt=True,
                reason=(
                    f"{account_state.consecutive_losses} pertes consécutives "
                    f"(seuil : {settings_.max_consecutive_losses})"
                ),
            )

        drawdown = account_state.daily_drawdown_percent
        if drawdown > settings_.max_daily_drawdown_percent:
            return ProtectionCheckResult(
                should_halt=True,
                reason=(
                    f"Drawdown journalier de {drawdown:.1f}% "
                    f"(seuil : {settings_.max_daily_drawdown_percent}%)"
                ),
            )

        return ProtectionCheckResult(should_halt=False)

    def apply(self, account_state: AccountState, settings_: RiskSettings) -> ProtectionCheckResult:
        """Évalue ET met à jour `account_state.trading_halted` en conséquence."""
        result = self.evaluate(account_state, settings_)
        account_state.trading_halted = result.should_halt
        account_state.halt_reason = result.reason or ""
        account_state.save(update_fields=["trading_halted", "halt_reason", "updated_at"])
        return result

    def register_trade_result(self, account_state: AccountState, is_win: bool, pnl: float) -> None:
        """À appeler après la clôture d'un trade (voir apps.journal)."""
        account_state.balance += pnl
        account_state.consecutive_losses = 0 if is_win else account_state.consecutive_losses + 1
        account_state.save(update_fields=["balance", "consecutive_losses", "updated_at"])

    def reset_daily_counters(self, account_state: AccountState, today) -> None:
        """À appeler une fois par jour (ex: tâche Celery à minuit)."""
        account_state.day_start_balance = account_state.balance
        account_state.last_reset_date = today
        account_state.trading_halted = False
        account_state.halt_reason = ""
        account_state.save(update_fields=[
            "day_start_balance", "last_reset_date", "trading_halted", "halt_reason", "updated_at",
        ])
