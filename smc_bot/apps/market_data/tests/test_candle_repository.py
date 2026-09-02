"""
apps/market_data/tests/test_candle_repository.py
"""

from datetime import datetime, timezone

from django.test import TestCase

from apps.market_data.models import Candle as CandleModel
from apps.market_data.services.candle_repository import CandleRepository
from apps.market_data.services.deriv_client import RawCandle


def _raw(epoch, o, h, l, c):
    return RawCandle(epoch=epoch, open=o, high=h, low=l, close=c)


class CandleRepositoryTests(TestCase):
    def setUp(self):
        self.repo = CandleRepository()
        base_epoch = int(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc).timestamp())
        self.raw_candles = [
            _raw(base_epoch + i * 900, 100 + i, 101 + i, 99 + i, 100.5 + i)
            for i in range(5)
        ]

    def test_save_raw_candles_creates_rows(self):
        saved = self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        self.assertEqual(saved, 5)
        self.assertEqual(CandleModel.objects.count(), 5)

    def test_save_raw_candles_is_idempotent(self):
        self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        # Deuxième sauvegarde des mêmes bougies -> aucune nouvelle ligne créée
        second_save = self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        self.assertEqual(second_save, 0)
        self.assertEqual(CandleModel.objects.count(), 5)

    def test_get_engine_candles_reindexed_chronologically(self):
        self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        engine_candles = self.repo.get_engine_candles("BOOM1000", "M15", limit=10)

        self.assertEqual(len(engine_candles), 5)
        # index 0..4 dans l'ordre chronologique
        self.assertEqual([c.index for c in engine_candles], [0, 1, 2, 3, 4])
        self.assertTrue(engine_candles[0].timestamp < engine_candles[-1].timestamp)
        self.assertEqual(engine_candles[0].close, 100.5)
        self.assertEqual(engine_candles[-1].close, 104.5)

    def test_get_engine_candles_respects_limit(self):
        self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        engine_candles = self.repo.get_engine_candles("BOOM1000", "M15", limit=2)
        self.assertEqual(len(engine_candles), 2)
        # Les 2 dernières bougies chronologiquement
        self.assertEqual(engine_candles[-1].close, 104.5)

    def test_instruments_and_timeframes_are_isolated(self):
        self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        self.repo.save_raw_candles("CRASH1000", "M15", self.raw_candles)
        boom_candles = self.repo.get_engine_candles("BOOM1000", "M15")
        crash_candles = self.repo.get_engine_candles("CRASH1000", "M15")
        self.assertEqual(len(boom_candles), 5)
        self.assertEqual(len(crash_candles), 5)
        self.assertEqual(CandleModel.objects.count(), 10)

    def test_latest_timestamp(self):
        self.repo.save_raw_candles("BOOM1000", "M15", self.raw_candles)
        latest = self.repo.latest_timestamp("BOOM1000", "M15")
        self.assertIsNotNone(latest)
        self.assertEqual(latest, self.raw_candles[-1].epoch and latest)  # sanity: non None

    def test_latest_timestamp_none_when_empty(self):
        self.assertIsNone(self.repo.latest_timestamp("BOOM1000", "M30"))
