from datetime import datetime, timezone
from apps.scanner.models import Symbol, MarketData
from core.adapters.deriv_adapter import DerivAdapter


class DataEngine:
    def __init__(self, broker_adapter=None):
        self.broker = broker_adapter or DerivAdapter()

    def fetch_and_store(self, symbol_name: str, timeframe: str, count: int = 100):
        symbol, _ = Symbol.objects.get_or_create(
            name=symbol_name,
            defaults={'asset_class': 'forex'}
        )

        candles = self.broker.get_market_data(symbol_name, timeframe, count)

        created_count = 0
        for candle in candles:
            ts = datetime.fromtimestamp(candle['timestamp'], tz=timezone.utc)
            _, created = MarketData.objects.get_or_create(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                defaults={
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle['volume'],
                }
            )
            if created:
                created_count += 1

        return created_count