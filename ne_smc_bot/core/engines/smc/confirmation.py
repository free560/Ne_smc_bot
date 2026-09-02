import pandas as pd
from core.engines.smc.structure import (
    load_candles, detect_swing_points, classify_structure, determine_trend,
    detect_bos, detect_choch, detect_liquidity, detect_liquidity_sweeps,
    detect_order_blocks, score_order_blocks, detect_fvg,
    calculate_premium_discount, get_price_zone,
    get_multi_htf_bias, check_multi_htf_alignment,
)


def find_best_zone(order_blocks: list[dict], direction: str) -> dict | None:
    """Retourne le meilleur Order Block actif (non mitigé) dans la direction voulue."""
    candidates = [ob for ob in order_blocks if ob['type'] == direction and not ob['is_mitigated']]
    if not candidates:
        return None
    return max(candidates, key=lambda ob: ob['quality_score'])


def check_retest(df: pd.DataFrame, zone: dict) -> dict:
    """Vérifie si le prix est revenu toucher la zone de l'Order Block après sa formation."""
    candles_after = df[df['timestamp'] > zone['timestamp']]
    for _, candle in candles_after.iterrows():
        if candle['low'] <= zone['zone_high'] and candle['high'] >= zone['zone_low']:
            return {'retested': True, 'retest_timestamp': candle['timestamp'], 'retest_candle': candle}
    return {'retested': False}


def check_confirmation_candle(retest_candle, direction: str) -> bool:
    """
    Vérifie que la bougie de retest est bien une bougie de rejet dans le bon sens :
    - bullish : clôture au-dessus de son ouverture (bougie verte de rejet)
    - bearish : clôture en dessous de son ouverture (bougie rouge de rejet)
    """
    if retest_candle is None:
        return False
    if direction == 'bullish':
        return retest_candle['close'] > retest_candle['open']
    return retest_candle['close'] < retest_candle['open']


def compute_risk_reward(entry: float, stop: float, target: float, direction: str) -> float | None:
    if direction == 'bullish':
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target

    if risk <= 0:
        return None
    return round(reward / risk, 2)


def run_confirmation_engine(symbol_name: str, ltf_timeframe: str = 'H1', min_rr: float = 1.5) -> dict:
    """
    Applique la checklist complète du Confirmation Engine et retourne
    une décision BUY / SELL / NO_TRADE avec le détail de chaque critère.
    """
    checklist = {}
    df = load_candles(symbol_name, ltf_timeframe)

    if df.empty:
        return {'decision': 'NO_TRADE', 'reason': 'Aucune donnée disponible', 'checklist': {}}

    df = detect_swing_points(df)
    labeled = classify_structure(df)
    ltf_trend = determine_trend(labeled)

    # --- Critère 1 : HTF Bias ---
    multi_htf = get_multi_htf_bias(symbol_name)
    alignment = check_multi_htf_alignment(ltf_trend, multi_htf)
    checklist['htf_bias'] = alignment['aligned']

    if not alignment['aligned']:
        return {
            'decision': 'NO_TRADE',
            'reason': alignment['reason'],
            'checklist': checklist,
        }

    direction = 'bullish' if ltf_trend == 'bullish' else 'bearish'

    # --- Critère 2 : Liquidity Sweep récent ---
    liquidity = detect_liquidity(labeled)
    sweeps = detect_liquidity_sweeps(df, liquidity)
    checklist['liquidity_sweep'] = len(sweeps) > 0
    if not checklist['liquidity_sweep']:
        return {'decision': 'NO_TRADE', 'reason': "Aucun Liquidity Sweep détecté", 'checklist': checklist}

    # --- Critère 3 : BOS dans le sens de la tendance ---
    bos_events = detect_bos(df, labeled)
    matching_bos = [b for b in bos_events if b['type'] == direction]
    checklist['bos'] = len(matching_bos) > 0
    if not checklist['bos']:
        return {'decision': 'NO_TRADE', 'reason': f"Aucun BOS {direction} confirmé", 'checklist': checklist}

    # --- Critère 4 : Order Block actif dans le bon sens ---
    order_blocks = detect_order_blocks(df, bos_events)
    order_blocks = score_order_blocks(df, order_blocks, sweeps)
    best_ob = find_best_zone(order_blocks, direction)
    checklist['order_block'] = best_ob is not None
    if not checklist['order_block']:
        return {'decision': 'NO_TRADE', 'reason': f"Aucun Order Block {direction} actif disponible", 'checklist': checklist}

    # --- Critère 5 : Retest de l'Order Block ---
    retest = check_retest(df, best_ob)
    checklist['retest'] = retest['retested']
    if not checklist['retest']:
        return {'decision': 'NO_TRADE', 'reason': "L'Order Block n'a pas encore été retesté", 'checklist': checklist}

    # --- Critère 6 : Bougie de confirmation au retest ---
    confirmed = check_confirmation_candle(retest.get('retest_candle'), direction)
    checklist['confirmation_candle'] = confirmed
    if not confirmed:
        return {'decision': 'NO_TRADE', 'reason': "Pas de bougie de confirmation au retest", 'checklist': checklist}

    # --- Calcul Entry / SL / TP / RR ---
    entry = float(retest['retest_candle']['close'])
    buffer = (best_ob['zone_high'] - best_ob['zone_low']) * 0.1  # petite marge de sécurité

    if direction == 'bullish':
        stop = best_ob['zone_low'] - buffer
        target_pools = [p['level'] for p in liquidity['buy_side'] if p['level'] > entry]
        target = min(target_pools) if target_pools else entry + (entry - stop) * min_rr
    else:
        stop = best_ob['zone_high'] + buffer
        target_pools = [p['level'] for p in liquidity['sell_side'] if p['level'] < entry]
        target = max(target_pools) if target_pools else entry - (stop - entry) * min_rr

    rr = compute_risk_reward(entry, stop, target, direction)

    # --- Critère 7 : Risk Reward minimum ---
    checklist['min_risk_reward'] = rr is not None and rr >= min_rr
    if not checklist['min_risk_reward']:
        return {
            'decision': 'NO_TRADE',
            'reason': f"Risk Reward insuffisant ({rr} < {min_rr})" if rr else "Risk Reward invalide",
            'checklist': checklist,
        }

    # Confidence Score : combine la qualité de l'Order Block et la marge de RR ---
    ob_score_component = best_ob['quality_score'] * 0.6  # poids 60%
    rr_ratio = rr / min_rr if min_rr > 0 else 1
    rr_component = min(100, rr_ratio * 50) * 0.4 # poids 40%, plafonné
    confidence_score = round(min(100, ob_score_component + rr_component), 1)

    # Tous les critères sont passés
    return {
        'decision': 'BUY' if direction == 'bullish' else 'SELL',
        'reason': "Tous les critères de la checklist sont validés",
        'checklist': checklist,
        'entry': round(entry, 5),
        'stop_loss': round(stop, 5),
        'take_profit': round(target, 5),
        'risk_reward': rr,
        'confidence_score': confidence_score,
        'symbol': symbol_name,
        'timeframe': ltf_timeframe,
    }