from django.core.management.base import BaseCommand
from core.engines.smc.signal_engine import generate_and_save_signal


class Command(BaseCommand):
    help = "Génère et sauvegarde un signal de trading pour un symbole"

    def add_arguments(self, parser):
        parser.add_argument('symbol', type=str)
        parser.add_argument('--timeframe', type=str, default='H1')
        parser.add_argument('--min-rr', type=float, default=1.5)

    def handle(self, *args, **options):
        result = generate_and_save_signal(options['symbol'], options['timeframe'], options['min_rr'])

        self.stdout.write(f"\nDécision : {result['decision']}")
        self.stdout.write(f"Raison : {result['reason']}")

        if result['decision'] in ('BUY', 'SELL'):
            self.stdout.write(f"Confidence Score : {result['confidence_score']}/100")
            if result['saved']:
                self.stdout.write(self.style.SUCCESS(f"Signal sauvegardé (ID: {result['signal_id']})"))
            else:
                self.stdout.write(self.style.WARNING(f"Non sauvegardé : {result['reason_not_saved']}"))