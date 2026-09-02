from celery import shared_task
from django.contrib.auth import get_user_model
from apps.brokers.models import BrokerAccount
from apps.signals.models import Signal
from core.engines.smc.signal_engine import generate_and_save_signal
from core.engines.risk.risk_engine import evaluate_signal_for_execution

User = get_user_model()



@shared_task
def generate_signal_task(symbol_name: str, timeframe: str = 'H1', min_rr: float = 1.5):
    result = generate_and_save_signal(symbol_name, timeframe, min_rr)

    if result['decision'] in ('BUY', 'SELL') and result.get('saved'):
        return f"{symbol_name} {timeframe}: {result['decision']} sauvegardé (ID {result['signal_id']}, confiance {result['confidence_score']})"
    elif result['decision'] in ('BUY', 'SELL'):
        return f"{symbol_name} {timeframe}: {result['decision']} détecté mais non sauvegardé ({result.get('reason_not_saved')})"
    else:
        return f"{symbol_name} {timeframe}: NO_TRADE ({result['reason']})"


@shared_task
def evaluate_pending_signals_task(username: str, broker_account_id: int):
    user = User.objects.get(username=username)
    broker_account = BrokerAccount.objects.get(id=broker_account_id)

    pending_signals = Signal.objects.filter(is_evaluated=False).order_by('created_at')

    if not pending_signals.exists():
        return "Aucun signal en attente d'évaluation"

    summaries = []
    for signal in pending_signals:
        result = evaluate_signal_for_execution(signal, user, broker_account)

        signal.is_evaluated = True
        signal.execution_allowed = result['can_execute']
        if result['can_execute']:
            signal.lot_size = result['lot_size']
            summaries.append(f"{signal.symbol} {signal.direction.upper()}: autorisé (lot {result['lot_size']})")
        else:
            summaries.append(f"{signal.symbol} {signal.direction.upper()}: refusé ({'; '.join(result['reasons'])})")
        signal.save()

    return f"{pending_signals.count()} signal(s) évalué(s) — " + " | ".join(summaries)