from django.core.management.base import BaseCommand
from apps.brokers.models import BrokerAccount
from core.engines.analytics.analytics_engine import compute_analytics


class Command(BaseCommand):
    help = "Affiche les statistiques de performance globales"

    def add_arguments(self, parser):
        parser.add_argument('--broker-account-id', type=int, default=None)

    def handle(self, *args, **options):
        broker_account = None
        if options['broker_account_id']:
            broker_account = BrokerAccount.objects.get(id=options['broker_account_id'])

        stats = compute_analytics(broker_account)

        if stats['total_trades'] == 0:
            self.stdout.write(self.style.WARNING("Aucun trade fermé pour l'instant."))
            return

        self.stdout.write(f"\n=== Analytics ({stats['total_trades']} trades) ===\n")
        self.stdout.write(f"Win Rate       : {stats['win_rate']}%")
        self.stdout.write(f"Wins/Losses/BE : {stats['wins']}/{stats['losses']}/{stats['breakevens']}")
        self.stdout.write(f"Profit Factor  : {stats['profit_factor']}")
        self.stdout.write(f"Net Profit     : {stats['net_profit']}")
        self.stdout.write(f"Max Drawdown   : {stats['max_drawdown']}")
        self.stdout.write(f"Sharpe Ratio*  : {stats['sharpe_ratio']}")
        self.stdout.write(self.style.WARNING("\n*Sharpe simplifié (par trade) — peu significatif avec un petit échantillon."))