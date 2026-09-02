from django.utils import timezone
from apps.execution.models import Order, Position
from apps.journal.models import TradeJournal


class ExecutionError(Exception):
    pass


def execute_signal(signal, user, broker_account, lot_size: float, mode: str = 'paper'):
    """
    Exécute un signal selon le mode demandé.
    Modes supportés : 'backtest', 'paper', 'demo', 'live'.
    """
    valid_modes = ('backtest', 'paper', 'demo', 'live')
    if mode not in valid_modes:
        raise ExecutionError(f"Mode invalide : {mode}")

    # --- Verrou de sécurité pour le mode LIVE (non négociable) ---
    if mode == 'live':
        if not user.is_live_trading_allowed:
            raise ExecutionError(
                "Trading LIVE refusé : l'utilisateur n'a pas explicitement activé "
                "le trading en argent réel (is_live_trading_allowed=False)."
            )
        if broker_account.account_type != 'live':
            raise ExecutionError(
                "Trading LIVE refusé : le compte broker sélectionné n'est pas un compte live."
            )
        if broker_account.user_id != user.id:
            raise ExecutionError(
                "Trading LIVE refusé : ce compte broker n'appartient pas à cet utilisateur."
            )

    # --- Modes simulés (backtest / paper) : aucun appel réseau, juste des écritures en base ---
    if mode in ('backtest', 'paper'):
        order = Order.objects.create(
            broker_account=broker_account,
            signal=signal,
            symbol=signal.symbol,
            direction=signal.direction,
            lot_size=lot_size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            status='filled',
            mode=mode,
        )
        position = Position.objects.create(
            order=order,
            current_price=signal.entry_price,
            pnl=0,
            is_open=True,
        )
        return {
            'success': True,
            'mode': mode,
            'order_id': order.id,
            'position_id': position.id,
            'message': f"Ordre {mode} simulé créé avec succès",
        }

    # --- Mode DEMO : appel réel au broker, avec les identifiants propres à CET utilisateur ---
    if mode == 'demo':
        if broker_account.account_type != 'demo':
            raise ExecutionError("Le compte broker sélectionné n'est pas un compte démo.")
        if broker_account.user_id != user.id:
            raise ExecutionError("Ce compte broker n'appartient pas à cet utilisateur.")
        if not broker_account.is_connected:
            raise ExecutionError("Ce compte broker n'est pas connecté — vérifiez les identifiants.")

        from core.adapters.broker_factory import get_adapter_for_account
        adapter = get_adapter_for_account(broker_account)

        broker_result = adapter.place_order(
            symbol=signal.symbol.name,
            direction=signal.direction,
            lot_size=lot_size,
            stop_loss=float(signal.stop_loss),
            take_profit=float(signal.take_profit),
            entry_price=float(signal.entry_price),
        )

        if not broker_result['success']:
            raise ExecutionError(f"Échec de l'ordre broker : {broker_result['error']}")

        order = Order.objects.create(
            broker_account=broker_account,
            signal=signal,
            symbol=signal.symbol,
            direction=signal.direction,
            lot_size=lot_size,
            entry_price=broker_result['buy_price'],
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            status='filled',
            mode='demo',
        )
        position = Position.objects.create(
            order=order,
            current_price=broker_result['buy_price'],
            pnl=0,
            is_open=True,
        )
        return {
            'success': True,
            'mode': 'demo',
            'order_id': order.id,
            'position_id': position.id,
            'broker_contract_id': broker_result['contract_id'],
            'message': f"Ordre DEMO réel placé sur {broker_account.broker_name} (contract_id {broker_result['contract_id']})",
        }

    # --- Mode LIVE : nécessite encore la connexion à un broker configuré pour le live ---
    raise ExecutionError(f"Le mode '{mode}' n'est pas encore implémenté.")


def update_open_positions(broker_account):
    """
    Met à jour le PnL de toutes les positions ouvertes pour ce compte,
    en comparant au prix actuel (dernière bougie M5 disponible).
    """
    from apps.scanner.models import MarketData

    open_positions = Position.objects.filter(order__broker_account=broker_account, is_open=True)
    updated = []

    for position in open_positions:
        latest_candle = MarketData.objects.filter(
            symbol=position.order.symbol, timeframe='M5'
        ).order_by('-timestamp').first()

        if latest_candle is None:
            continue

        current_price = float(latest_candle.close)
        entry = float(position.order.entry_price)
        lot_size = float(position.order.lot_size)
        contract_size = 100_000

        if position.order.direction == 'buy':
            pnl = (current_price - entry) * lot_size * contract_size
        else:
            pnl = (entry - current_price) * lot_size * contract_size

        position.current_price = current_price
        position.pnl = round(pnl, 2)
        position.save()
        updated.append(position.id)

    return updated



def check_and_close_positions(broker_account):
    from apps.execution.models import Trade

    open_positions = Position.objects.filter(order__broker_account=broker_account, is_open=True)
    closed = []

    for position in open_positions:
        order = position.order
        current_price = float(position.current_price)
        sl = float(position.current_stop_loss or order.stop_loss)
        tp = float(order.take_profit)

        hit_sl = (order.direction == 'buy' and current_price <= sl) or \
                 (order.direction == 'sell' and current_price >= sl)
        hit_tp = (order.direction == 'buy' and current_price >= tp) or \
                 (order.direction == 'sell' and current_price <= tp)

        if hit_sl or hit_tp:
            position.is_open = False
            position.closed_at = timezone.now()
            position.save()

            result = 'win' if hit_tp else ('breakeven' if hit_sl and position.is_breakeven_applied else 'loss')

            trade = Trade.objects.create(
                position=position,
                result=result,
                profit_loss=position.pnl,
            )

            signal_reason = order.signal.reason if order.signal else "Signal non disponible"
            TradeJournal.objects.create(
                trade=trade,
                notes=(
                    f"{order.direction.upper()} {order.symbol} | Entry: {order.entry_price} | "
                    f"SL final: {sl} | TP: {tp} | Mode: {order.mode} | "
                    f"Raison du signal: {signal_reason}"
                ),
            )

            closed.append({'position_id': position.id, 'result': result})

    return closed

def apply_breakeven_and_trailing(broker_account, breakeven_trigger_pct: float = 0.5, trailing_distance_pct: float = 0.3):
    """
    Pour chaque position ouverte :
    - Si le prix a progressé d'au moins breakeven_trigger_pct de la distance TP, déplace le SL à l'entrée.
    - Une fois en breakeven, active un trailing stop qui suit le prix à trailing_distance_pct de distance.
    """
    open_positions = Position.objects.filter(order__broker_account=broker_account, is_open=True)
    updated = []

    for position in open_positions:
        order = position.order
        entry = float(order.entry_price)
        tp = float(order.take_profit)
        current_price = float(position.current_price)
        current_sl = float(position.current_stop_loss or order.stop_loss)

        distance_to_tp = abs(tp - entry)
        if order.direction == 'buy':
            progress = (current_price - entry) / distance_to_tp if distance_to_tp > 0 else 0
        else:
            progress = (entry - current_price) / distance_to_tp if distance_to_tp > 0 else 0

        changed = False

        # --- Break Even ---
        if not position.is_breakeven_applied and progress >= breakeven_trigger_pct:
            new_sl = entry
            if order.direction == 'buy' and new_sl > current_sl:
                current_sl = new_sl
                changed = True
            elif order.direction == 'sell' and new_sl < current_sl:
                current_sl = new_sl
                changed = True

            if changed:
                position.is_breakeven_applied = True
                position.trailing_stop_active = True

        # --- Trailing Stop (seulement après le Break Even) ---
        elif position.trailing_stop_active:
            trail_distance = distance_to_tp * trailing_distance_pct
            if order.direction == 'buy':
                new_sl = current_price - trail_distance
                if new_sl > current_sl:
                    current_sl = new_sl
                    changed = True
            else:
                new_sl = current_price + trail_distance
                if new_sl < current_sl:
                    current_sl = new_sl
                    changed = True

        if changed:
            position.current_stop_loss = round(current_sl, 5)
            position.save()
            updated.append({'position_id': position.id, 'new_sl': position.current_stop_loss})

    return updated