def calculate_position_size(
    balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss: float,
    contract_size: int = 100_000,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
) -> dict:
    """
    Calcule la taille de position (en lots) pour risquer exactement
    risk_per_trade_pct % du solde, compte tenu de la distance au Stop Loss.
    """
    stop_distance = abs(entry_price - stop_loss)

    if stop_distance <= 0:
        return {'valid': False, 'reason': 'Distance au Stop Loss invalide (nulle ou négative)'}

    risk_amount = balance * (risk_per_trade_pct / 100)

    # Unités de la devise de base nécessaires pour que ce risk_amount corresponde au stop_distance
    position_units = risk_amount / stop_distance
    lot_size = position_units / contract_size

    # Applique les limites du broker
    clamped = False
    if lot_size < min_lot:
        lot_size = min_lot
        clamped = True
    elif lot_size > max_lot:
        lot_size = max_lot
        clamped = True

    lot_size = round(lot_size, 2)
    actual_risk_amount = lot_size * contract_size * stop_distance

    return {
        'valid': True,
        'lot_size': lot_size,
        'risk_amount_requested': round(risk_amount, 2),
        'risk_amount_actual': round(actual_risk_amount, 2),
        'clamped_to_broker_limits': clamped,
    }