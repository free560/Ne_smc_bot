from celery import shared_task
from core.engines.data_engine import DataEngine


@shared_task
def fetch_market_data_task(symbol_name: str, timeframe: str, count: int = 100):
    engine = DataEngine()
    created = engine.fetch_and_store(symbol_name, timeframe, count)
    return f"{symbol_name} {timeframe}: {created} nouvelles bougies"