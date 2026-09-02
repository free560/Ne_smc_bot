"""
apps/scanner/tests/test_scanner_service.py

Test d'intégration : CandleRepository (DB réelle) -> DecisionEngine -> SignalRepository.
"""

from datetime import datetime, timezone

from django.test import TestCase

from apps.market_data.models import TimeframeChoice
from apps.market_data.services.candle_repository import CandleRepository
from apps.market_data.services.deriv_client import RawCandle
from apps.scanner.services.scanner_service import InsufficientDataError, ScannerService
from apps.signals.models import SignalRecord
from apps.smc.services.dtos import Direction


def _flat_series(n=40, base_epoch=1_755_000_000, step=900):
    return [
        RawCandle(epoch=base_epoch + i * step, open=100, high=100.2, low=99.8, close=100 + (0.05 if i % 2 == 0 else -0.05))
        for i in range(n)
    ]


class ScannerServiceTests(TestCase):
    def setUp(self):
        self.candle_repo = CandleRepository()
        self.scanner = ScannerService(candle_repository=self.candle_repo)

    def test_raises_when_not_enough_data(self):
        with self.assertRaises(InsufficientDataError):
            self.scanner.scan_instrument("BOOM1000")

    def test_scan_flat_market_returns_no_trade_and_persists(self):
        for tf in (TimeframeChoice.M30, TimeframeChoice.M15, TimeframeChoice.M1):
            self.candle_repo.save_raw_candles("BOOM1000", tf, _flat_series())

        signal = self.scanner.scan_instrument("BOOM1000")

        self.assertEqual(signal.direction, Direction.NO_TRADE)
        self.assertEqual(SignalRecord.objects.count(), 1)
        record = SignalRecord.objects.first()
        self.assertEqual(record.instrument, "BOOM1000")
        self.assertEqual(record.direction, "NO_TRADE")

    def test_scan_without_persist_does_not_save(self):
        for tf in (TimeframeChoice.M30, TimeframeChoice.M15, TimeframeChoice.M1):
            self.candle_repo.save_raw_candles("CRASH1000", tf, _flat_series())

        self.scanner.scan_instrument("CRASH1000", persist=False)
        self.assertEqual(SignalRecord.objects.count(), 0)

    def test_scan_all_handles_missing_instrument_gracefully(self):
        for tf in (TimeframeChoice.M30, TimeframeChoice.M15, TimeframeChoice.M1):
            self.candle_repo.save_raw_candles("BOOM1000", tf, _flat_series())
        # CRASH1000 n'a aucune donnée -> ne doit pas planter le scan global

        results = self.scanner.scan_all(["BOOM1000", "CRASH1000"])

        self.assertIsNotNone(results["BOOM1000"])
        self.assertIsNone(results["CRASH1000"])
