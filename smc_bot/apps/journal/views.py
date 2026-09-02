"""
apps/journal/views.py

CRUD fin, mais avec une règle métier importante : quand un trade passe
de OPEN à WIN/LOSS avec un pnl renseigné, on répercute automatiquement
le résultat sur l'AccountState (apps.risk) via le CapitalProtectionEngine,
pour que le Risk Center reste toujours synchronisé avec le journal réel.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.services.audit_service import AuditService
from apps.journal.forms import TradeJournalEntryForm
from apps.journal.models import TradeJournalEntry, TradeResult
from apps.risk.models import AccountState, RiskSettings
from apps.risk.services.capital_protection_engine import CapitalProtectionEngine


@login_required
def entry_list(request):
    entries = TradeJournalEntry.objects.filter(user=request.user)
    context = {"module_title": "Journal de Trading", "entries": entries}
    return render(request, "journal/list.html", context)


@login_required
def entry_create(request):
    if request.method == "POST":
        form = TradeJournalEntryForm(request.POST, request.FILES)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            _apply_result_to_account(request, entry, previous_result=TradeResult.OPEN)
            AuditService.log("JOURNAL_ENTRY_CREATED", user=request.user, details={"entry_id": entry.id})
            return redirect("journal:list")
    else:
        form = TradeJournalEntryForm()

    context = {"module_title": "Nouveau Trade", "form": form}
    return render(request, "journal/form.html", context)


@login_required
def entry_update(request, pk):
    entry = get_object_or_404(TradeJournalEntry, pk=pk, user=request.user)
    previous_result = entry.result

    if request.method == "POST":
        form = TradeJournalEntryForm(request.POST, request.FILES, instance=entry)
        if form.is_valid():
            entry = form.save()
            _apply_result_to_account(request, entry, previous_result=previous_result)
            AuditService.log("JOURNAL_ENTRY_UPDATED", user=request.user, details={"entry_id": entry.id})
            return redirect("journal:list")
    else:
        form = TradeJournalEntryForm(instance=entry)

    context = {"module_title": "Modifier le Trade", "form": form, "entry": entry}
    return render(request, "journal/form.html", context)


@login_required
def entry_delete(request, pk):
    entry = get_object_or_404(TradeJournalEntry, pk=pk, user=request.user)
    if request.method == "POST":
        entry.delete()
        AuditService.log("JOURNAL_ENTRY_DELETED", user=request.user, details={"entry_id": pk})
        return redirect("journal:list")
    context = {"module_title": "Supprimer le Trade", "entry": entry}
    return render(request, "journal/confirm_delete.html", context)


def _apply_result_to_account(request, entry: TradeJournalEntry, previous_result: str) -> None:
    """Répercute la clôture d'un trade (OPEN -> WIN/LOSS) sur l'AccountState."""
    just_closed = previous_result == TradeResult.OPEN and entry.result in (TradeResult.WIN, TradeResult.LOSS)
    if not just_closed or entry.pnl is None:
        return

    account_state, _ = AccountState.objects.get_or_create(user=request.user)
    risk_settings, _ = RiskSettings.objects.get_or_create(user=request.user)

    engine = CapitalProtectionEngine()
    engine.register_trade_result(account_state, is_win=(entry.result == TradeResult.WIN), pnl=entry.pnl)
    result = engine.apply(account_state, risk_settings)

    if result.should_halt:
        AuditService.log("TRADING_HALTED", user=request.user, details={"reason": result.reason})

        from apps.notifications.services.notification_dispatcher import NotificationDispatcher

        event_type = "DRAWDOWN_ALERT" if "Drawdown" in (result.reason or "") else "CONSECUTIVE_LOSS_ALERT"
        NotificationDispatcher().dispatch(
            event_type, f"Trading arrêté : {result.reason}", user=request.user
        )
