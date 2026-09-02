from django.core.management.base import BaseCommand
from core.engines.smc.structure import (
    load_candles, detect_swing_points, classify_structure, determine_trend,
    detect_bos, detect_choch, detect_liquidity, detect_liquidity_sweeps,
    detect_order_blocks, score_order_blocks, detect_fvg,
    calculate_premium_discount, get_price_zone,
    get_htf_bias, check_htf_alignment, get_multi_htf_bias, check_multi_htf_alignment
)

class Command(BaseCommand):
    help = "Analyse la structure de marché (HH/HL/LH/LL + tendance + BOS) pour un symbole"

    def add_arguments(self, parser):
        parser.add_argument('symbol', type=str)
        parser.add_argument('--timeframe', type=str, default='H1')

    def handle(self, *args, **options):
        df = load_candles(options['symbol'], options['timeframe'])

        if df.empty:
            self.stdout.write(self.style.ERROR("Aucune donnée trouvée — lance d'abord fetch_data."))
            return

        df = detect_swing_points(df)
        labeled = classify_structure(df)
        trend = determine_trend(labeled)
        bos_events = detect_bos(df, labeled)
        choch_events = detect_choch(df, labeled)
        liquidity = detect_liquidity(labeled)
        sweeps = detect_liquidity_sweeps(df, liquidity)
        order_blocks = detect_order_blocks(df, bos_events)
        order_blocks = score_order_blocks(df, order_blocks, sweeps)
        fvgs = detect_fvg(df)


        self.stdout.write(f"\n{options['symbol']} {options['timeframe']} — {len(labeled)} swing points détectés\n")
        for s in labeled[-10:]:
            self.stdout.write(f"  {s['timestamp']} | {s['type'].upper():5} | {s['price']:.5f} | {s['label']}")

        self.stdout.write(self.style.SUCCESS(f"\nTendance actuelle : {trend.upper()}"))

        self.stdout.write(f"\n{len(bos_events)} BOS détecté(s) :\n")
        for b in bos_events[-5:]:
            self.stdout.write(
                f"  {b['confirmed_timestamp']} | BOS {b['type'].upper():8} | "
                f"niveau cassé: {b['broken_level']:.5f} | clôture: {b['confirmed_price']:.5f}"
            )

        self.stdout.write(f"\n{len(choch_events)} CHoCH détecté(s) :\n")
        for c in choch_events[-5:]:
            self.stdout.write(
                f"  {c['confirmed_timestamp']} | CHoCH {c['type'].upper():8} | "
                f"niveau cassé: {c['broken_level']:.5f} | clôture: {c['confirmed_price']:.5f}"
            )

        self.stdout.write(f"\n{len(liquidity['buy_side'])} zone(s) Buy Side Liquidity (Equal Highs) :\n")
        for pool in liquidity['buy_side']:
            self.stdout.write(
                f"  niveau: {pool['level']:.5f} | {pool['touches']} touches | "
                f"de {pool['first_timestamp']} à {pool['last_timestamp']}"
            )

        self.stdout.write(f"\n{len(liquidity['sell_side'])} zone(s) Sell Side Liquidity (Equal Lows) :\n")
        for pool in liquidity['sell_side']:
            self.stdout.write(
                f"  niveau: {pool['level']:.5f} | {pool['touches']} touches | "
                f"de {pool['first_timestamp']} à {pool['last_timestamp']}"
            )

        self.stdout.write(f"\n{len(sweeps)} Liquidity Sweep(s) détecté(s) :\n")
        for sw in sweeps:
            self.stdout.write(
                f"  {sw['timestamp']} | {sw['type'].upper()} | "
                f"niveau: {sw['pool_level']:.5f} | mèche: {sw['wick_price']:.5f} | clôture: {sw['close_price']:.5f}"
            )


        self.stdout.write(f"\n{len(order_blocks)} Order Block(s) détecté(s), triés par qualité :\n")
        for ob in order_blocks:
            status = "mitigé" if ob['is_mitigated'] else "actif"
            self.stdout.write(
                f"  Score {ob['quality_score']:5.1f} | {ob['timestamp']} | {ob['type'].upper():8} | "
                f"zone: {ob['zone_low']:.5f} - {ob['zone_high']:.5f} | {status}"
            ) 


        self.stdout.write(f"\n{len(fvgs)} Fair Value Gap(s) détecté(s) :\n")
        for fvg in fvgs[-5:]:
            status = "comblé" if fvg['is_filled'] else "ouvert"
            self.stdout.write(
                f"  {fvg['timestamp']} | {fvg['type'].upper():8} | "
                f"zone: {fvg['zone_low']:.5f} - {fvg['zone_high']:.5f} | {status}"
            )


        pd_zones = calculate_premium_discount(labeled)
        current_price = df.iloc[-1]['close']
        current_zone = get_price_zone(current_price, pd_zones)

        if pd_zones:
            self.stdout.write(f"\nZones Premium/Discount :\n")
            self.stdout.write(f"  Range : {pd_zones['range_low']:.5f} - {pd_zones['range_high']:.5f}")
            self.stdout.write(f"  Equilibrium (50%) : {pd_zones['equilibrium']:.5f}")
            self.stdout.write(f"  Prix actuel : {current_price:.5f} → Zone {current_zone.upper()}")


        multi_htf = get_multi_htf_bias(options['symbol'])
        multi_alignment = check_multi_htf_alignment(trend, multi_htf)

        self.stdout.write(f"\nBiais D1 : {multi_htf['D1']['trend'].upper()}")
        self.stdout.write(f"Biais H4 : {multi_htf['H4']['trend'].upper()}")
        self.stdout.write(f"Biais HTF combiné : {multi_htf['overall'].upper()}")
        self.stdout.write(f"Alignement LTF/HTF : {'OUI' if multi_alignment['aligned'] else 'NON'}")
        self.stdout.write(f"  → {multi_alignment['reason']}")        