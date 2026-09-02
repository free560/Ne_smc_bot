from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from apps.brokers.models import BrokerAccount
from apps.execution.models import Trade, Position
from apps.signals.models import Signal
from core.engines.analytics.analytics_engine import compute_analytics


@login_required
def dashboard(request):
    broker_accounts = BrokerAccount.objects.filter(user=request.user)
    primary_account = broker_accounts.filter(is_connected=True).first() or broker_accounts.first()

    balance = float(primary_account.balance) if primary_account else 0

    open_positions = Position.objects.filter(
        order__broker_account__user=request.user, is_open=True
    ).select_related('order', 'order__symbol').order_by('-opened_at')

    unrealized_pnl = sum(float(p.pnl) for p in open_positions)
    equity = balance + unrealized_pnl

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timezone.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def pnl_since(start):
        return Trade.objects.filter(
            position__order__broker_account__user=request.user, closed_at__gte=start
        ).aggregate(total=Sum('profit_loss'))['total'] or 0

    daily_pnl = pnl_since(today_start)
    weekly_pnl = pnl_since(week_start)
    monthly_pnl = pnl_since(month_start)

    stats = compute_analytics(primary_account) if primary_account else {'total_trades': 0}

    recent_signals = Signal.objects.select_related('symbol').order_by('-created_at')[:5]

    context = {
        'balance': round(balance, 2),
        'equity': round(equity, 2),
        'daily_pnl': round(float(daily_pnl), 2),
        'weekly_pnl': round(float(weekly_pnl), 2),
        'monthly_pnl': round(float(monthly_pnl), 2),
        'win_rate': stats.get('win_rate'),
        'profit_factor': stats.get('profit_factor'),
        'max_drawdown': stats.get('max_drawdown'),
        'total_trades': stats.get('total_trades', 0),
        'open_positions': open_positions,
        'open_positions_count': open_positions.count(),
        'recent_signals': recent_signals,
        'has_broker_account': primary_account is not None,
    }
    return render(request, 'dashboard/dashboard.html', context)
    