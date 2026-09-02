import statistics
from apps.execution.models import Trade


def compute_analytics(broker_account=None) -> dict:
    qs = Trade.objects.all().order_by('closed_at')
    if broker_account:
        qs = qs.filter(position__order__broker_account=broker_account)

    trades = list(qs)
    total = len(trades)

    if total == 0:
        return {'total_trades': 0}

    wins = [t for t in trades if t.result == 'win']
    losses = [t for t in trades if t.result == 'loss']
    breakevens = [t for t in trades if t.result == 'breakeven']

    win_rate = round(len(wins) / total * 100, 2)

    gross_profit = sum(float(t.profit_loss) for t in wins)
    gross_loss = abs(sum(float(t.profit_loss) for t in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    net_profit = round(sum(float(t.profit_loss) for t in trades), 2)

    # Courbe d'équité → Max Drawdown
    equity = 0
    peak = 0
    max_drawdown = 0
    for t in trades:
        equity += float(t.profit_loss)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    # Sharpe simplifié : par trade, non annualisé — indicatif tant que l'historique est court
    returns = [float(t.profit_loss) for t in trades]
    sharpe = None
    if len(returns) > 1 and statistics.stdev(returns) > 0:
        sharpe = round(statistics.mean(returns) / statistics.stdev(returns), 2)

    return {
        'total_trades': total,
        'wins': len(wins),
        'losses': len(losses),
        'breakevens': len(breakevens),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'net_profit': net_profit,
        'max_drawdown': round(max_drawdown, 2),
        'sharpe_ratio': sharpe,
    }