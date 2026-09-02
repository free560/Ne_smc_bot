from django.utils import timezone
from datetime import timedelta
from apps.scanner.models import Symbol, MarketData
from apps.signals.models import Signal
from core.engines.smc.confirmation import run_confirmation_engine


def generate_and_save_signal(symbol_name: str, timeframe: str = 'H1', min_rr: float = 1.5) -> dict:
    result = run_confirmation_engine(symbol_name, timeframe, min_rr)

    if result['decision'] not in ('BUY', 'SELL'):
        return {**result, 'saved': False, 'reason_not_saved': result['reason']}

    symbol, _ = Symbol.objects.get_or_create(name=symbol_name, defaults={'asset_class': 'forex'})

    # Récupère la bougie la plus récente utilisée dans ce calcul
    latest_candle = MarketData.objects.filter(
        symbol=symbol, timeframe=timeframe
    ).order_by('-timestamp').first()

    if latest_candle is None:
        return {**result, 'saved': False, 'reason_not_saved': 'Aucune donnée de marché disponible'}

    # Dernier signal identique (même sens) déjà enregistré
    existing = Signal.objects.filter(
        symbol=symbol, timeframe=timeframe, direction=result['decision'].lower(),
    ).order_by('-created_at').first()

    if existing:
        same_price = abs(float(existing.entry_price) - result['entry']) / result['entry'] < 0.001
        # Le signal existant a-t-il été généré APRÈS l'arrivée de cette dernière bougie ?
        no_new_data = existing.created_at >= latest_candle.timestamp

        if same_price and no_new_data:
            return {**result, 'saved': False, 'reason_not_saved': 'Aucune nouvelle donnée depuis le dernier signal identique'}

    signal = Signal.objects.create(
        symbol=symbol,
        timeframe=timeframe, 
        direction=result['decision'].lower(),
        entry_price=result['entry'], 
        stop_loss=result['stop_loss'], 
        take_profit=result['take_profit'],
        risk_reward=result['risk_reward'], 
        confidence_score=int(result['confidence_score']),
        reason=result['reason'],
    )

    return {**result, 'saved': True, 'signal_id': signal.id}