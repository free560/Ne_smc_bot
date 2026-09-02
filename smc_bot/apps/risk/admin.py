from django.contrib import admin
from .models import RiskSettings, AccountState


@admin.register(RiskSettings)
class RiskSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "risk_per_trade_percent", "min_risk_reward",
                     "max_consecutive_losses", "max_daily_drawdown_percent")


@admin.register(AccountState)
class AccountStateAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "consecutive_losses", "trading_halted", "updated_at")
    list_filter = ("trading_halted",)
