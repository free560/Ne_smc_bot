from celery import shared_task
from django.contrib.auth import get_user_model
from apps.signals.models import Signal
from apps.brokers.models import BrokerAccount
from core.engines.execution.execution_engine import (
    execute_signal, update_open_positions, apply_breakeven_and_trailing,
    check_and_close_positions, ExecutionError
)

User = get_user_model()


@shared_task
def execute_pending_task(username: str, broker_account_id: int, mode: str = 'paper'):
    user = User.objects.get(username=username)
    broker_account = BrokerAccount.objects.get(id=broker_account_id)

    pending = Signal.objects.filter(
        is_evaluated=True, execution_allowed=True, orders__isnull=True
    )

    executed = []
    for signal in pending:
        try:
            result = execute_signal(signal, user, broker_account, float(signal.lot_size), mode)
            executed.append(f"{signal.symbol} {signal.direction.upper()} (Order {result['order_id']})")
        except ExecutionError as e:
            executed.append(f"{signal.symbol}: refusé ({e})")

    updated = update_open_positions(broker_account)
    breakeven_updates = apply_breakeven_and_trailing(broker_account)
    closed = check_and_close_positions(broker_account)

    summary = f"{len(executed)} exécuté(s), {len(updated)} position(s) mise(s) à jour, {len(closed)} fermée(s)"
    if closed:
        summary += " [" + ", ".join(f"{c['result'].upper()}" for c in closed) + "]"

    return summary 



