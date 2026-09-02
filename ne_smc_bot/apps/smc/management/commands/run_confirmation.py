from django.core.management.base import BaseCommand
from core.engines.smc.confirmation import run_confirmation_engine


class Command(BaseCommand):
    help = "Exécute le Confirmation Engine complet pour un symbole"

    def add_arguments(self, parser):
        parser.add_argument('symbol', type=str)
        parser.add_argument('--timeframe', type=str, default='H1')
        parser.add_argument('--min-rr', type=float, default=1.5)

    def handle(self, *args, **options):
        result = run_confirmation_engine(options['symbol'], options['timeframe'], options['min_rr'])

        self.stdout.write(f"\n=== Confirmation Engine : {options['symbol']} {options['timeframe']} ===\n")

        for criterion, passed in result['checklist'].items():
            icon = "✅" if passed else "❌"
            self.stdout.write(f"  {icon} {criterion}")

        self.stdout.write(f"\nRaison : {result['reason']}")

        if result['decision'] in ('BUY', 'SELL'):
            self.stdout.write(self.style.SUCCESS(f"\nDÉCISION : {result['decision']}"))
            self.stdout.write(f"  Entry : {result['entry']}")
            self.stdout.write(f"  Stop Loss : {result['stop_loss']}")
            self.stdout.write(f"  Take Profit : {result['take_profit']}")
            self.stdout.write(f"  Risk/Reward : {result['risk_reward']}")
        else:
            self.stdout.write(self.style.WARNING(f"\nDÉCISION : {result['decision']}"))