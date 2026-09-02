from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.signals.models import Signal
from apps.brokers.models import BrokerAccount
from core.engines.execution.execution_engine import (
    execute_signal, update_open_positions, check_and_close_positions, ExecutionError
)

User = get_user_model()


class Command(BaseCommand):
    help = "Exécute (en mode paper) les signaux évalués et autorisés qui n'ont pas encore d'ordre"

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('broker_account_id', type=int)
        parser.add_argument('--mode', type=str, default='paper')

    def handle(self, *args, **options):
        user = User.objects.get(username=options['username'])
        broker_account = BrokerAccount.objects.get(id=options['broker_account_id'])

        pending = Signal.objects.filter(
            is_evaluated=True, execution_allowed=True, orders__isnull=True
        )

        for signal in pending:
            try:
                result = execute_signal(signal, user, broker_account, float(signal.lot_size), options['mode'])
                self.stdout.write(self.style.SUCCESS(f" {result['message']} (Order ID {result['order_id']})"))
            except ExecutionError as e:
                self.stdout.write(self.style.ERROR(f" {signal}: {e}"))

        self.stdout.write("\nMise à jour des positions ouvertes...")
        updated = update_open_positions(broker_account)
        self.stdout.write(f"  {len(updated)} position(s) mise(s) à jour")

        closed = check_and_close_positions(broker_account)
        for c in closed:
            self.stdout.write(f"  Position {c['position_id']} fermée : {c['result'].upper()}")