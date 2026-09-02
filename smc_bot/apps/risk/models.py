"""
apps/risk/models.py

RiskSettings   : paramètres de risque configurables par l'utilisateur.
AccountState   : état courant du capital (solde, pertes consécutives,
                  drawdown du jour, statut d'arrêt) utilisé par le
                  CapitalProtectionEngine pour décider STOP TRADING ou non.
"""
from django.conf import settings
from django.db import models


class RiskSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_settings")

    risk_per_trade_percent = models.FloatField(default=1.0, help_text="0.5 / 1 / 2 %")
    min_risk_reward = models.FloatField(default=2.0)
    max_positions_per_setup = models.IntegerField(default=2)
    max_consecutive_losses = models.IntegerField(default=3)
    max_daily_drawdown_percent = models.FloatField(default=20.0)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Réglages risque de {self.user.username}"


class AccountState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_state")

    balance = models.FloatField(default=0.0)
    day_start_balance = models.FloatField(default=0.0)
    consecutive_losses = models.IntegerField(default=0)
    trading_halted = models.BooleanField(default=False)
    halt_reason = models.CharField(max_length=255, blank=True, default="")
    last_reset_date = models.DateField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "ARRÊTÉ" if self.trading_halted else "actif"
        return f"Compte de {self.user.username} - {self.balance} ({status})"

    @property
    def daily_drawdown_percent(self) -> float:
        if not self.day_start_balance:
            return 0.0
        return max(0.0, (self.day_start_balance - self.balance) / self.day_start_balance * 100)
