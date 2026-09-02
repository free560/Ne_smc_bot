from django.core.management.base import BaseCommand
from core.engines.data_engine import DataEngine


class Command(BaseCommand):
    help = "Récupère les données de marché pour un symbole donné"

    def add_arguments(self, parser):
        parser.add_argument('symbol', type=str)
        parser.add_argument('--timeframe', type=str, default='H1')
        parser.add_argument('--count', type=int, default=100)

    def handle(self, *args, **options):
        engine = DataEngine()
        created = engine.fetch_and_store(options['symbol'], options['timeframe'], options['count'])
        self.stdout.write(self.style.SUCCESS(f"{created} nouvelles bougies enregistrées."))