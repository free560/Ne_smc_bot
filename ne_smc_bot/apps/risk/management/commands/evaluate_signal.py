from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.signals.models import Signal
from apps.brokers.models import BrokerAccount
from core.engines.risk.risk_engine import evaluate_signal_for_execution

User = get_user_model()


class Command(BaseCommand):
    help = "Évalue si un signal peut être exécuté selon le Risk Engine, et calcule le lot size"

    def add_arguments(self, parser):
        parser.add_argument('signal_id', type=int)
        parser.add_argument('username', type=str)
        parser.add_argument('broker_account_id', type=int)

    def handle(self, *args, **options):
        signal = Signal.objects.get(id=options['signal_id'])
        user = User.objects.get(username=options['username'])
        broker_account = BrokerAccount.objects.get(id=options['broker_account_id'])

        result = evaluate_signal_for_execution(signal, user, broker_account)

        self.stdout.write(f"\nSignal : {signal.symbol} {signal.direction.upper()} @ {signal.entry_price}\n")

        if result['can_execute']:
            self.stdout.write(self.style.SUCCESS(f"Exécution autorisée"))
            self.stdout.write(f"  Lot size : {result['lot_size']}")
            self.stdout.write(f"  Montant risqué : {result['risk_amount']}")
            if result['clamped']:
                self.stdout.write(self.style.WARNING("Lot size ajusté aux limites broker"))
        else:
            self.stdout.write(self.style.ERROR(" Exécution refusée"))
            for reason in result['reasons']:
                self.stdout.write(f"  - {reason}")