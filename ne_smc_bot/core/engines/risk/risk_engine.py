from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from apps.execution.models import Position, Trade
from core.engines.risk.position_sizing import calculate_position_size


def check_risk_limits(user, broker_account) -> dict:
    """
    Vérifie si un nouveau trade est autorisé selon les RiskSettings de l'utilisateur.
    Retourne allowed=True/False avec le détail des raisons de blocage.
    """
    risk_settings = getattr(user, 'risk_settings', None)
    if risk_settings is None:
        return {'allowed': False, 'reasons': ["Aucun RiskSettings configuré pour cet utilisateur"]}

    reasons = []
    now = timezone.now()

    # Max positions ouvertes
    open_positions_count = Position.objects.filter(
        order__broker_account=broker_account, is_open=True
    ).count()
    if open_positions_count >= risk_settings.max_open_positions:
        reasons.append(
            f"Limite de positions ouvertes atteinte ({open_positions_count}/{risk_settings.max_open_positions})"
        )

    # --- Drawdown journalier ---
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_pnl = Trade.objects.filter(
        position__order__broker_account=broker_account, closed_at__gte=today_start
    ).aggregate(total=Sum('profit_loss'))['total'] or 0

    daily_loss_pct = (abs(daily_pnl) / float(broker_account.balance) * 100) if daily_pnl < 0 else 0
    if daily_loss_pct >= float(risk_settings.daily_drawdown_limit):
        reasons.append(
            f"Drawdown journalier atteint ({daily_loss_pct:.2f}% / {risk_settings.daily_drawdown_limit}%)"
        )

    # --- Drawdown hebdomadaire ---
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_pnl = Trade.objects.filter(
        position__order__broker_account=broker_account, closed_at__gte=week_start
    ).aggregate(total=Sum('profit_loss'))['total'] or 0

    weekly_loss_pct = (abs(weekly_pnl) / float(broker_account.balance) * 100) if weekly_pnl < 0 else 0
    if weekly_loss_pct >= float(risk_settings.weekly_drawdown_limit):
        reasons.append(
            f"Drawdown hebdomadaire atteint ({weekly_loss_pct:.2f}% / {risk_settings.weekly_drawdown_limit}%)"
        )

    # --- Drawdown global (depuis toujours) ---
    global_pnl = Trade.objects.filter(
        position__order__broker_account=broker_account
    ).aggregate(total=Sum('profit_loss'))['total'] or 0

    global_loss_pct = (abs(global_pnl) / float(broker_account.balance) * 100) if global_pnl < 0 else 0
    if global_loss_pct >= float(risk_settings.global_drawdown_limit):
        reasons.append(
            f"Drawdown global atteint ({global_loss_pct:.2f}% / {risk_settings.global_drawdown_limit}%)"
        )

    return {
        'allowed': len(reasons) == 0,
        'reasons': reasons,
        'risk_per_trade_pct': float(risk_settings.risk_per_trade),
    }


def evaluate_signal_for_execution(signal, user, broker_account) -> dict:
    """
    Combine Risk Engine + Position Sizing pour déterminer si un signal
    peut être exécuté, et avec quelle taille de position.
    """
    risk_check = check_risk_limits(user, broker_account)

    if not risk_check['allowed']:
        return {
            'can_execute': False,
            'reasons': risk_check['reasons'],
        }

    sizing = calculate_position_size(
        balance=float(broker_account.balance),
        risk_per_trade_pct=risk_check['risk_per_trade_pct'],
        entry_price=float(signal.entry_price),
        stop_loss=float(signal.stop_loss),
    )

    if not sizing['valid']:
        return {'can_execute': False, 'reasons': [sizing['reason']]}

    return {
        'can_execute': True,
        'lot_size': sizing['lot_size'],
        'risk_amount': sizing['risk_amount_actual'],
        'clamped': sizing['clamped_to_broker_limits'],
    }    