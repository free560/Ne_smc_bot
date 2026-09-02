"""
apps/scanner/management/commands/run_scan.py

Usage :
    python manage.py run_scan                       # scan BOOM1000 + CRASH1000
    python manage.py run_scan --instrument BOOM1000  # un seul instrument
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.market_data.models import Instrument
from apps.scanner.services.scanner_service import InsufficientDataError, ScannerService


class Command(BaseCommand):
    help = "Lance le DecisionEngine sur les données déjà en base et affiche/persiste le signal."

    def add_arguments(self, parser):
        parser.add_argument("--instrument", choices=[c.value for c in Instrument], default=None)

    def handle(self, *args, **options):
        service = ScannerService()
        instruments = [options["instrument"]] if options["instrument"] else [c.value for c in Instrument]

        for instrument in instruments:
            self.stdout.write(f"Scan de {instrument}...")
            try:
                signal = service.scan_instrument(instrument)
            except InsufficientDataError as exc:
                self.stdout.write(self.style.WARNING(f"  -> {exc}"))
                continue

            if signal.is_tradeable:
                style = self.style.SUCCESS
            else:
                style = self.style.NOTICE

            self.stdout.write(style(
                f"  -> {signal.direction.value}"
                + (f" ({signal.scenario}, confiance {signal.confidence_score}%)" if signal.is_tradeable else "")
            ))
            if signal.is_tradeable:
                self.stdout.write(
                    f"     Entry={signal.entry}  SL={signal.stop_loss}  "
                    f"TP={signal.take_profit}  RR=1:{signal.risk_reward}"
                )
            for reason in signal.reasons:
                self.stdout.write(f"     - {reason}")
