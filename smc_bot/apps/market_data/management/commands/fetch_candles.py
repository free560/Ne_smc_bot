"""
apps/market_data/management/commands/fetch_candles.py

Usage :
    python manage.py fetch_candles --instrument BOOM1000 --timeframe M15 --count 300
    python manage.py fetch_candles --all          # toutes les combinaisons instrument x timeframe
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.market_data.models import Instrument, TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.market_data.services.deriv_client import DerivClient, DerivConnectionError


class Command(BaseCommand):
    help = "Récupère l'historique de bougies OHLC depuis Deriv et le sauvegarde en base."

    def add_arguments(self, parser):
        parser.add_argument("--instrument", choices=[c.value for c in Instrument], default=None)
        parser.add_argument("--timeframe", choices=[c.value for c in TimeframeChoice], default=None)
        parser.add_argument("--count", type=int, default=500)
        parser.add_argument("--all", action="store_true", help="Récupère toutes les combinaisons instrument x timeframe")

    def handle(self, *args, **options):
        is_legacy_endpoint = "ws.derivws.com" in settings.DERIV_WS_URL
        if is_legacy_endpoint and not settings.DERIV_APP_ID:
            raise CommandError(
                "DERIV_APP_ID n'est pas configuré. Renseigne-le dans ton fichier .env "
                "(voir .env.example)."
            )

        client = DerivClient(
            app_id=settings.DERIV_APP_ID,
            api_token=settings.DERIV_API_TOKEN,
            ws_url=settings.DERIV_WS_URL,
        )
        repository = CandleRepository()

        if options["all"]:
            combos = [(i.value, t.value) for i in Instrument for t in TimeframeChoice]
        else:
            if not options["instrument"] or not options["timeframe"]:
                raise CommandError("Précise --instrument et --timeframe, ou utilise --all.")
            combos = [(options["instrument"], options["timeframe"])]

        for instrument, timeframe in combos:
            self.stdout.write(f"Récupération {instrument} {timeframe}...")
            try:
                saved = repository.fetch_and_store(client, instrument, timeframe, count=options["count"])
                self.stdout.write(self.style.SUCCESS(f"  -> {saved} nouvelles bougies sauvegardées"))
            except DerivConnectionError as exc:
                self.stdout.write(self.style.ERROR(f"  -> Connexion échouée : {exc}"))
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"  -> Erreur : {exc}"))
