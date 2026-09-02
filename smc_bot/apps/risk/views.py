"""
apps/risk/views.py
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.risk.models import AccountState, RiskSettings
from apps.risk.services.capital_protection_engine import CapitalProtectionEngine
from apps.risk.services.position_size_engine import PositionSizeEngine


@login_required
def overview(request):
    risk_settings, _ = RiskSettings.objects.get_or_create(user=request.user)
    account_state, _ = AccountState.objects.get_or_create(user=request.user)

    if request.method == "POST":
        risk_settings.risk_per_trade_percent = float(request.POST.get("risk_per_trade_percent", risk_settings.risk_per_trade_percent))
        risk_settings.min_risk_reward = float(request.POST.get("min_risk_reward", risk_settings.min_risk_reward))
        risk_settings.max_positions_per_setup = int(request.POST.get("max_positions_per_setup", risk_settings.max_positions_per_setup))
        risk_settings.max_consecutive_losses = int(request.POST.get("max_consecutive_losses", risk_settings.max_consecutive_losses))
        risk_settings.max_daily_drawdown_percent = float(request.POST.get("max_daily_drawdown_percent", risk_settings.max_daily_drawdown_percent))
        risk_settings.save()
        return redirect("risk:overview")

    protection_result = CapitalProtectionEngine().evaluate(account_state, risk_settings)

    context = {
        "module_title": "Risk Center",
        "risk_settings": risk_settings,
        "account_state": account_state,
        "protection_result": protection_result,
    }
    return render(request, "risk/overview.html", context)


@login_required
def position_size_calculator(request):
    result = None
    if request.method == "POST":
        account_state, _ = AccountState.objects.get_or_create(user=request.user)
        risk_settings, _ = RiskSettings.objects.get_or_create(user=request.user)

        entry = float(request.POST.get("entry"))
        stop_loss = float(request.POST.get("stop_loss"))
        risk_percent = float(request.POST.get("risk_percent", risk_settings.risk_per_trade_percent))

        result = PositionSizeEngine().calculate(account_state.balance, risk_percent, entry, stop_loss)

    context = {"module_title": "Calculateur de Lot Size", "result": result}
    return render(request, "risk/position_size_calculator.html", context)
