import pandas as pd
from apps.scanner.models import MarketData


def load_candles(symbol_name: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """Charge les bougies depuis la base, triées chronologiquement."""
    qs = (
        MarketData.objects
        .filter(symbol__name=symbol_name, timeframe=timeframe)
        .order_by('-timestamp')[:limit]
    )
    data = list(qs.values('timestamp', 'open', 'high', 'low', 'close'))
    df = pd.DataFrame(data)
    df = df.sort_values('timestamp').reset_index(drop=True)
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    return df


def detect_swing_points(df: pd.DataFrame, lookback: int = 2) -> pd.DataFrame:
    """
    Marque chaque bougie comme swing_high / swing_low.
    lookback = nombre de bougies à comparer de chaque côté.
    """
    df = df.copy()
    df['swing_high'] = False
    df['swing_low'] = False

    for i in range(lookback, len(df) - lookback):
        window_high = df['high'].iloc[i - lookback: i + lookback + 1]
        window_low = df['low'].iloc[i - lookback: i + lookback + 1]

        if df['high'].iloc[i] == window_high.max():
            df.at[i, 'swing_high'] = True

        if df['low'].iloc[i] == window_low.min():
            df.at[i, 'swing_low'] = True

    return df


def classify_structure(df: pd.DataFrame) -> list[dict]:
    """
    Parcourt les swing points dans l'ordre chronologique et les classe
    en HH, HL, LH, LL par rapport au swing précédent du même type.
    """
    swings = []

    for i, row in df.iterrows():
        if row['swing_high']:
            swings.append({'index': i, 'type': 'high', 'price': row['high'], 'timestamp': row['timestamp']})
        elif row['swing_low']:
            swings.append({'index': i, 'type': 'low', 'price': row['low'], 'timestamp': row['timestamp']})

    labeled = []
    last_high = None
    last_low = None

    for swing in swings:
        if swing['type'] == 'high':
            if last_high is not None:
                label = 'HH' if swing['price'] > last_high else 'LH'
            else:
                label = 'H'
            last_high = swing['price']
        else:
            if last_low is not None:
                label = 'HL' if swing['price'] > last_low else 'LL'
            else:
                label = 'L'
            last_low = swing['price']

        labeled.append({**swing, 'label': label})

    return labeled


def determine_trend(labeled_swings: list[dict]) -> str:
    """
    Détermine la tendance à partir des 4 derniers swings labellisés.
    Bullish : succession de HH et HL
    Bearish : succession de LH et LL
    Range : mélange incohérent
    """
    recent = [s['label'] for s in labeled_swings[-4:] if s['label'] in ('HH', 'HL', 'LH', 'LL')]

    if not recent:
        return 'undefined'

    bullish_signals = recent.count('HH') + recent.count('HL')
    bearish_signals = recent.count('LH') + recent.count('LL')

    if bullish_signals > bearish_signals:
        return 'bullish'
    elif bearish_signals > bullish_signals:
        return 'bearish'
    return 'range'


def detect_bos(df: pd.DataFrame, labeled_swings: list[dict]) -> list[dict]:
    """
    Détecte les BOS (Break of Structure) : continuation de tendance.
    Un BOS bullish casse le dernier HH, un BOS bearish casse le dernier LL.
    """
    bos_events = []

    last_hh = None
    last_ll = None

    for swing in labeled_swings:
        if swing['label'] == 'HH':
            last_hh = swing
        elif swing['label'] == 'LL':
            last_ll = swing

        # Cherche, après ce swing, une bougie qui clôture au-delà
        candles_after = df[df['timestamp'] > swing['timestamp']]

        if last_hh is not None:
            breakout = candles_after[
                (candles_after['timestamp'] > last_hh['timestamp']) &
                (candles_after['close'] > last_hh['price'])
            ]
            if not breakout.empty:
                first_break = breakout.iloc[0]
                bos_events.append({
                    'type': 'bullish',
                    'broken_level': last_hh['price'],
                    'broken_swing_timestamp': last_hh['timestamp'],
                    'confirmed_timestamp': first_break['timestamp'],
                    'confirmed_price': first_break['close'],
                })
                last_hh = None  # évite de re-signaler le même BOS

        if last_ll is not None:
            breakout = candles_after[
                (candles_after['timestamp'] > last_ll['timestamp']) &
                (candles_after['close'] < last_ll['price'])
            ]
            if not breakout.empty:
                first_break = breakout.iloc[0]
                bos_events.append({
                    'type': 'bearish',
                    'broken_level': last_ll['price'],
                    'broken_swing_timestamp': last_ll['timestamp'],
                    'confirmed_timestamp': first_break['timestamp'],
                    'confirmed_price': first_break['close'],
                })
                last_ll = None

    # Trie chronologiquement par date de confirmation
    bos_events.sort(key=lambda e: e['confirmed_timestamp'])
    return bos_events


def detect_choch(df: pd.DataFrame, labeled_swings: list[dict]) -> list[dict]:
    """
    Détecte les CHoCH (Change of Character) : rupture de la structure
    dans le sens OPPOSÉ à la tendance en cours = signal de retournement potentiel.
    """
    choch_events = []
    current_trend = None  # 'bullish' ou 'bearish', déduit au fil de l'eau

    last_hl = None  # dernier Higher Low (support de la tendance bullish)
    last_lh = None  # dernier Lower High (résistance de la tendance bearish)

    for swing in labeled_swings:
        # Met à jour la tendance en cours à chaque nouveau HH/LL confirmé
        if swing['label'] == 'HH':
            current_trend = 'bullish'
        elif swing['label'] == 'LL':
            current_trend = 'bearish'

        if swing['label'] == 'HL':
            last_hl = swing
        elif swing['label'] == 'LH':
            last_lh = swing

        candles_after = df[df['timestamp'] > swing['timestamp']]

        # En tendance bullish : un CHoCH bearish casse le dernier HL à la baisse
        if current_trend == 'bullish' and last_hl is not None:
            breakout = candles_after[
                (candles_after['timestamp'] > last_hl['timestamp']) &
                (candles_after['close'] < last_hl['price'])
            ]
            if not breakout.empty:
                first_break = breakout.iloc[0]
                choch_events.append({
                    'type': 'bearish',
                    'broken_level': last_hl['price'],
                    'broken_swing_timestamp': last_hl['timestamp'],
                    'confirmed_timestamp': first_break['timestamp'],
                    'confirmed_price': first_break['close'],
                })
                current_trend = 'bearish'
                last_hl = None

        # En tendance bearish : un CHoCH bullish casse le dernier LH à la hausse
        if current_trend == 'bearish' and last_lh is not None:
            breakout = candles_after[
                (candles_after['timestamp'] > last_lh['timestamp']) &
                (candles_after['close'] > last_lh['price'])
            ]
            if not breakout.empty:
                first_break = breakout.iloc[0]
                choch_events.append({
                    'type': 'bullish',
                    'broken_level': last_lh['price'],
                    'broken_swing_timestamp': last_lh['timestamp'],
                    'confirmed_timestamp': first_break['timestamp'],
                    'confirmed_price': first_break['close'],
                })
                current_trend = 'bullish'
                last_lh = None

    choch_events.sort(key=lambda e: e['confirmed_timestamp'])
    return choch_events


def detect_liquidity(labeled_swings: list[dict], tolerance_pct: float = 0.05) -> dict:
    """
    Regroupe les swing highs/lows proches en zones de liquidité.
    tolerance_pct = écart maximum en % du prix pour considérer deux niveaux comme "égaux".
    Retourne : {'buy_side': [...], 'sell_side': [...]}
    """
    highs = [s for s in labeled_swings if s['type'] == 'high']
    lows = [s for s in labeled_swings if s['type'] == 'low']

    def group_equal_levels(swings: list[dict]) -> list[dict]:
        pools = []
        used = set()

        for i, swing_a in enumerate(swings):
            if i in used:
                continue
            group = [swing_a]
            used.add(i)

            for j, swing_b in enumerate(swings):
                if j in used or j == i:
                    continue
                diff_pct = abs(swing_a['price'] - swing_b['price']) / swing_a['price'] * 100
                if diff_pct <= tolerance_pct:
                    group.append(swing_b)
                    used.add(j)

            if len(group) >= 2:  # au moins 2 swings proches = une vraie zone de liquidité
                avg_price = sum(s['price'] for s in group) / len(group)
                pools.append({
                    'level': avg_price,
                    'touches': len(group),
                    'swings': group,
                    'first_timestamp': min(s['timestamp'] for s in group),
                    'last_timestamp': max(s['timestamp'] for s in group),
                })

        return pools

    buy_side = group_equal_levels(highs)   # Equal Highs
    sell_side = group_equal_levels(lows)   # Equal Lows

    return {'buy_side': buy_side, 'sell_side': sell_side}


def detect_liquidity_sweeps(df: pd.DataFrame, liquidity: dict) -> list[dict]:
    """
    Détecte les sweeps : le prix dépasse une zone de liquidité en mèche
    mais clôture en deçà (piège à liquidité, pas une vraie cassure).
    """
    sweeps = []

    # Sell Side Sweep : la mèche basse dépasse un pool sell-side, mais la clôture reste au-dessus
    for pool in liquidity['sell_side']:
        candles_after = df[df['timestamp'] > pool['last_timestamp']]
        for _, candle in candles_after.iterrows():
            if candle['low'] < pool['level'] and candle['close'] > pool['level']:
                sweeps.append({
                    'type': 'sell_side_sweep',
                    'pool_level': pool['level'],
                    'wick_price': candle['low'],
                    'close_price': candle['close'],
                    'timestamp': candle['timestamp'],
                })
                break  # un seul sweep signalé par pool, le premier qui se produit

    # Buy Side Sweep : la mèche haute dépasse un pool buy-side, mais la clôture reste en dessous
    for pool in liquidity['buy_side']:
        candles_after = df[df['timestamp'] > pool['last_timestamp']]
        for _, candle in candles_after.iterrows():
            if candle['high'] > pool['level'] and candle['close'] < pool['level']:
                sweeps.append({
                    'type': 'buy_side_sweep',
                    'pool_level': pool['level'],
                    'wick_price': candle['high'],
                    'close_price': candle['close'],
                    'timestamp': candle['timestamp'],
                })
                break

    sweeps.sort(key=lambda e: e['timestamp'])
    return sweeps


def detect_order_blocks(df: pd.DataFrame, bos_events: list[dict]) -> list[dict]:
    """
    Pour chaque BOS, identifie la dernière bougie opposée juste avant
    la bougie de confirmation — c'est l'Order Block.
    """
    order_blocks = []

    for bos in bos_events:
        # Bougies avant la confirmation du BOS
        candles_before = df[df['timestamp'] < bos['confirmed_timestamp']].reset_index(drop=True)

        if candles_before.empty:
            continue

        if bos['type'] == 'bullish':
            # On cherche la dernière bougie baissière (close < open) avant le BOS
            bearish_candles = candles_before[candles_before['close'] < candles_before['open']]
            if bearish_candles.empty:
                continue
            ob_candle = bearish_candles.iloc[-1]
            order_blocks.append({
                'type': 'bullish',
                'zone_high': ob_candle['open'],
                'zone_low': ob_candle['low'],
                'timestamp': ob_candle['timestamp'],
                'related_bos_timestamp': bos['confirmed_timestamp'],
                'is_mitigated': False,
            })

        else:  # bearish
            bullish_candles = candles_before[candles_before['close'] > candles_before['open']]
            if bullish_candles.empty:
                continue
            ob_candle = bullish_candles.iloc[-1]
            order_blocks.append({
                'type': 'bearish',
                'zone_high': ob_candle['high'],
                'zone_low': ob_candle['open'],
                'timestamp': ob_candle['timestamp'],
                'related_bos_timestamp': bos['confirmed_timestamp'],
                'is_mitigated': False,
            })

    # Vérifie si l'Order Block a déjà été "mitigé" (retesté) après sa formation
    for ob in order_blocks:
        candles_after = df[df['timestamp'] > ob['timestamp']]
        for _, candle in candles_after.iterrows():
            if ob['zone_low'] <= candle['low'] <= ob['zone_high'] or ob['zone_low'] <= candle['high'] <= ob['zone_high']:
                ob['is_mitigated'] = True
                break

    # Dédoublonne les OB identiques (peut arriver si plusieurs BOS partagent le même OB source)
    seen = set()
    unique_order_blocks = []
    for ob in order_blocks:
        key = (ob['type'], ob['timestamp'])
        if key not in seen:
            seen.add(key)
            unique_order_blocks.append(ob)
    order_blocks = unique_order_blocks  

    return order_blocks

  

    
def score_order_blocks(df: pd.DataFrame, order_blocks: list[dict], sweeps: list[dict]) -> list[dict]:
    """
    Attribue un score de qualité (0-100) à chaque Order Block,
    basé sur plusieurs critères de confluence SMC.
    """
    if df.empty:
        return order_blocks

    current_price = df.iloc[-1]['close']
    avg_range = (df['high'] - df['low']).mean()  # taille moyenne d'une bougie, pour relativiser

    sweep_timestamps = [sw['timestamp'] for sw in sweeps]

    for ob in order_blocks:
        score = 0

        # Critère 1 : fraîcheur (poids fort — 40 points)
        if not ob['is_mitigated']:
            score += 40

        # Critère 2 : taille de la zone relative à la moyenne (zone resserrée = mieux, max 20 points)
        zone_size = ob['zone_high'] - ob['zone_low']
        if avg_range > 0:
            size_ratio = zone_size / avg_range
            score += max(0, 20 - (size_ratio * 10))  # plus la zone est petite, plus le score est haut

        # Critère 3 : présence d'un sweep dans les bougies juste avant l'OB (20 points)
        recent_sweep = any(
            ob['timestamp'] - pd.Timedelta(hours=6) <= ts <= ob['timestamp']
            for ts in sweep_timestamps
        )
        if recent_sweep:
            score += 20

        # Critère 4 : proximité par rapport au prix actuel (max 20 points)
        distance_pct = abs(current_price - ob['zone_high']) / current_price * 100
        proximity_score = max(0, 20 - (distance_pct * 50))  # dégressif selon l'éloignement
        score += proximity_score

        ob['quality_score'] = round(min(100, max(0, score)), 1)

    return sorted(order_blocks, key=lambda x: x['quality_score'], reverse=True)

def detect_fvg(df: pd.DataFrame) -> list[dict]:
    """
    Détecte les Fair Value Gaps (FVG) : vides de prix sur 3 bougies consécutives.
    """
    fvgs = []

    for i in range(1, len(df) - 1):
        candle_1 = df.iloc[i - 1]
        candle_3 = df.iloc[i + 1]

        # FVG Bullish : gap entre le high de bougie 1 et le low de bougie 3
        if candle_3['low'] > candle_1['high']:
            fvgs.append({
                'type': 'bullish',
                'zone_high': candle_3['low'],
                'zone_low': candle_1['high'],
                'timestamp': df.iloc[i]['timestamp'],  # timestamp de la bougie centrale (impulsive)
                'is_filled': False,
            })

        # FVG Bearish : gap entre le low de bougie 1 et le high de bougie 3
        elif candle_3['high'] < candle_1['low']:
            fvgs.append({
                'type': 'bearish',
                'zone_high': candle_1['low'],
                'zone_low': candle_3['high'],
                'timestamp': df.iloc[i]['timestamp'],
                'is_filled': False,
            })

    # Vérifie si le FVG a été comblé (le prix est revenu dans la zone après sa formation)
    for fvg in fvgs:
        candles_after = df[df['timestamp'] > fvg['timestamp']]
        for _, candle in candles_after.iterrows():
            if candle['low'] <= fvg['zone_high'] and candle['high'] >= fvg['zone_low']:
                fvg['is_filled'] = True
                break

    return fvgs


def calculate_premium_discount(labeled_swings: list[dict], lookback: int = 10) -> dict | None:
    """
    Calcule les zones Premium/Discount à partir du range formé par
    le swing high et le swing low les plus significatifs récents.
    """
    recent_swings = labeled_swings[-lookback:]

    highs = [s['price'] for s in recent_swings if s['type'] == 'high']
    lows = [s['price'] for s in recent_swings if s['type'] == 'low']

    if not highs or not lows:
        return None

    range_high = max(highs)
    range_low = min(lows)
    equilibrium = (range_high + range_low) / 2

    return {
        'range_high': range_high,
        'range_low': range_low,
        'equilibrium': equilibrium,
        'premium_zone': (equilibrium, range_high),
        'discount_zone': (range_low, equilibrium),
    }


def get_price_zone(current_price: float, pd_zones: dict) -> str:
    """Détermine si le prix actuel est en zone Premium, Discount, ou à l'Equilibrium."""
    if pd_zones is None:
        return 'undefined'

    if current_price > pd_zones['equilibrium']:
        return 'premium'
    elif current_price < pd_zones['equilibrium']:
        return 'discount'
    return 'equilibrium'


def get_htf_bias(symbol_name: str, htf_timeframe: str = 'H4') -> dict:
    """
    Calcule le biais de tendance sur une timeframe supérieure (HTF),
    en réutilisant exactement la même logique que pour la timeframe d'exécution.
    """
    df_htf = load_candles(symbol_name, htf_timeframe)

    if df_htf.empty:
        return {'trend': 'undefined', 'timeframe': htf_timeframe}

    df_htf = detect_swing_points(df_htf)
    labeled_htf = classify_structure(df_htf)
    trend_htf = determine_trend(labeled_htf)

    return {'trend': trend_htf, 'timeframe': htf_timeframe}


def check_htf_alignment(ltf_trend: str, htf_bias: dict) -> dict:
    """
    Vérifie si la tendance de la timeframe d'exécution (LTF) est alignée
    avec le biais de la Higher Timeframe (HTF).
    """
    htf_trend = htf_bias['trend']

    if htf_trend == 'undefined' or ltf_trend == 'undefined':
        return {'aligned': False, 'reason': 'donnée insuffisante'}

    if htf_trend == 'range':
        return {'aligned': True, 'reason': f"HTF ({htf_bias['timeframe']}) en range — pas de biais directionnel imposé"}

    if ltf_trend == htf_trend:
        return {'aligned': True, 'reason': f"LTF aligné avec le biais {htf_bias['timeframe']} ({htf_trend.upper()})"}

    return {
        'aligned': False,
        'reason': f"LTF ({ltf_trend.upper()}) va à l'encontre du biais {htf_bias['timeframe']} ({htf_trend.upper()})"
    }

def get_multi_htf_bias(symbol_name: str) -> dict:
    """
    Calcule le biais sur les deux Higher Timeframes de référence : D1 et H4.
    """
    bias_d1 = get_htf_bias(symbol_name, htf_timeframe='D1')
    bias_h4 = get_htf_bias(symbol_name, htf_timeframe='H4')

    d1_trend = bias_d1['trend']
    h4_trend = bias_h4['trend']

    # Détermine le biais HTF global : D1 et H4 doivent être cohérents entre eux
    if d1_trend == 'undefined' or h4_trend == 'undefined':
        overall = 'undefined'
    elif d1_trend == h4_trend:
        overall = d1_trend
    elif d1_trend == 'range' or h4_trend == 'range':
        # Si l'un des deux est en range, on suit l'autre (plus directionnel)
        overall = h4_trend if d1_trend == 'range' else d1_trend
    else:
        # D1 et H4 se contredisent franchement (bullish vs bearish) — HTF incertain
        overall = 'conflicting'

    return {
        'D1': bias_d1,
        'H4': bias_h4,
        'overall': overall,
    }


def check_multi_htf_alignment(ltf_trend: str, multi_htf: dict) -> dict:
    """
    Vérifie l'alignement de la LTF avec le biais HTF combiné (D1 + H4).
    """
    overall = multi_htf['overall']

    if overall in ('undefined', 'conflicting'):
        return {
            'aligned': False,
            'reason': f"Biais HTF {overall} (D1={multi_htf['D1']['trend'].upper()}, "
                      f"H4={multi_htf['H4']['trend'].upper()}) — prudence requise, pas de biais clair"
        }

    if overall == 'range':
        return {'aligned': True, 'reason': "HTF (D1+H4) en range — pas de restriction directionnelle"}

    if ltf_trend == overall:
        return {'aligned': True, 'reason': f"LTF aligné avec le biais HTF combiné ({overall.upper()})"}

    return {
        'aligned': False,
        'reason': f"LTF ({ltf_trend.upper()}) va à l'encontre du biais HTF combiné ({overall.upper()})"
    }        