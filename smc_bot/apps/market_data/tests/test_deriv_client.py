"""
apps/market_data/tests/test_deriv_client.py

Aucun appel réseau réel : on simule les réponses WebSocket pour tester
le parsing et la gestion d'erreurs du DerivClient.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from apps.market_data.services.deriv_client import (
    DerivAPIError,
    DerivClient,
    DerivConnectionError,
    RawCandle,
)


class DerivClientParsingTests(unittest.TestCase):
    def setUp(self):
        self.client = DerivClient(app_id="1089", api_token="")

    def test_fetch_candles_parses_response(self):
        fake_response = {
            "candles": [
                {"epoch": 1000, "open": "100.1", "high": "101.2", "low": "99.5", "close": "100.8"},
                {"epoch": 1900, "open": "100.8", "high": "102.0", "low": "100.0", "close": "101.5"},
            ]
        }

        async def fake_request(payload):
            return fake_response

        with patch.object(self.client, "_request", AsyncMock(side_effect=fake_request)):
            candles = asyncio.run(self.client.fetch_candles_async("BOOM1000", 900, count=2))

        self.assertEqual(len(candles), 2)
        self.assertIsInstance(candles[0], RawCandle)
        self.assertEqual(candles[0].epoch, 1000)
        self.assertEqual(candles[0].close, 100.8)

    def test_fetch_candles_empty_when_no_candles_key(self):
        async def fake_request(payload):
            return {}

        with patch.object(self.client, "_request", AsyncMock(side_effect=fake_request)):
            candles = asyncio.run(self.client.fetch_candles_async("BOOM1000", 60, count=10))

        self.assertEqual(candles, [])

    def test_missing_app_id_raises(self):
        with self.assertRaises(ValueError):
            DerivClient(app_id="")

    def test_api_error_propagates(self):
        async def fake_request(payload):
            raise DerivAPIError("InvalidSymbol")

        with patch.object(self.client, "_request", AsyncMock(side_effect=fake_request)):
            with self.assertRaises(DerivAPIError):
                asyncio.run(self.client.fetch_candles_async("NOT_A_SYMBOL", 60))

    def test_connection_error_after_retries(self):
        async def always_fails(payload):
            raise DerivConnectionError("réseau injoignable")

        with patch.object(self.client, "_request", AsyncMock(side_effect=always_fails)):
            with self.assertRaises(DerivConnectionError):
                asyncio.run(self.client.fetch_candles_async("BOOM1000", 60))


if __name__ == "__main__":
    unittest.main()
