"""
apps/market_data/management/commands/stream_candles.py

Process longue durée : maintient une connexion WebSocket ouverte vers
Deriv et sauvegarde chaque mise à jour de bougie en base au fil de l'eau.
À lancer en tant que service séparé (systemd, supervisor, docker...),
PAS via Celery (qui n'est pas fait pour une connexion permanente).

Usage :
    python manage.py stream_candles --instrument BOOM1000 --timeframe M1
"""

from __future__ import annotations

import asyncio
import signal

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.market_data.models import Instrument, TimeframeChoice
from apps.market_data.services.candle_repository import TIMEFRAME_TO_GRANULARITY, CandleRepository
from apps.market_data.services.deriv_stream import DerivStream


class Command(BaseCommand):
    help = "Souscrit en temps réel aux bougies d'un instrument Deriv et les sauvegarde en continu."

    def add_arguments(self, parser):
        parser.add_argument("--instrument", choices=[c.value for c in Instrument], required=True)
        parser.add_argument("--timeframe", choices=[c.value for c in TimeframeChoice], required=True)

    def handle(self, *args, **options):
        if not settings.DERIV_APP_ID:
            raise CommandError("DERIV_APP_ID n'est pas configuré (voir .env).")

        instrument = options["instrument"]
        timeframe = options["timeframe"]
        granularity = TIMEFRAME_TO_GRANULARITY[timeframe]

        repository = CandleRepository()
        stream = DerivStream(app_id=settings.DERIV_APP_ID, ws_url=settings.DERIV_WS_URL)

        # Wrapper async-safe de l'appel ORM synchrone : évite
        # SynchronousOnlyOperation en déportant l'accès DB sur un thread dédié.
        save_raw_candles_async = sync_to_async(
            repository.save_raw_candles, thread_sensitive=True
        )

        async def on_candle(raw_candle):
            saved = await save_raw_candles_async(instrument, timeframe, [raw_candle])
            marker = "nouvelle" if saved else "mise à jour"
            self.stdout.write(f"[{instrument} {timeframe}] {marker} bougie : close={raw_candle.close}")

        loop = asyncio.new_event_loop()

        def _handle_stop(*_args):
            self.stdout.write(self.style.WARNING("Arrêt demandé, fermeture propre du flux..."))
            stream.stop()

        try:
            loop.add_signal_handler(signal.SIGINT, _handle_stop)
            loop.add_signal_handler(signal.SIGTERM, _handle_stop)
        except NotImplementedError:
            pass  # Windows ne supporte pas add_signal_handler -> Ctrl+C lèvera KeyboardInterrupt normalement

        self.stdout.write(f"Démarrage du flux temps réel {instrument} {timeframe}...")
        try:
            loop.run_until_complete(stream.run(instrument, granularity, on_candle))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Interrompu par l'utilisateur."))