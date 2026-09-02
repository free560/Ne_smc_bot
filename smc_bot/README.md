# SMC RSI BOOM & CRASH 1000 PRO BOT

Plateforme de signaux de trading (Boom 1000 / Crash 1000) basée sur les
Smart Money Concepts (structure, BOS, CHoCH, liquidité, order blocks, FVG)
combinés à une confirmation RSI. **Le système ne trade jamais automatiquement**
— il génère des signaux BUY / SELL / NO TRADE que l'utilisateur exécute
manuellement.

## Stack

- Python 3.12+ / Django 5
- SQLite (base par défaut)
- Templates Django + Tailwind CSS (CDN en dev) + Chart.js
- Celery + Redis (prévu pour le scanner temps réel et les notifications)

## Structure du projet

```
smc_bot/
├── manage.py
├── config/                # settings, urls, wsgi, asgi
├── apps/
│   ├── accounts/          # authentification, rôles
│   ├── dashboard/         # vue d'ensemble
│   ├── market_data/       # connexion Deriv API (WebSocket), stockage OHLC
│   ├── scanner/           # scan périodique Boom1000 / Crash1000
│   ├── smc/                # moteurs BOS, CHoCH, liquidité, order blocks, FVG
│   ├── indicators/        # RSI et futurs indicateurs
│   ├── signals/           # moteur de décision + génération BUY/SELL/NO TRADE
│   ├── risk/               # calcul du risque, lot size, capital protection
│   ├── journal/           # journal de trades
│   ├── analytics/         # win rate, profit factor, drawdown
│   ├── notifications/     # dashboard, Telegram, email
│   └── settings_app/      # préférences utilisateur (risk %, instruments...)
├── templates/
└── static/
```

Chaque app suit le **Service Layer Pattern** : la logique métier vit dans
`apps/<app>/services/`, les `views.py` restent minces (orchestration uniquement).

## Installation

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # puis renseigner les vraies valeurs
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## État actuel — Projet complet (Phases 1 à 5)

- ✅ Structure Django complète (12 apps, service layer, templates, static)
- ✅ **Moteur SMC/RSI complet** (`apps/smc`, `apps/indicators`, `apps/signals`) —
  structure de marché (HH/HL/LH/LL), BOS, CHoCH, liquidité, sweeps, order
  blocks, FVG, range filter, RSI (Wilder), les 4 scénarios de la stratégie,
  decision hierarchy complète.
- ✅ **Market Data** (`apps/market_data`) — modèles `Candle`/`FetchLog`,
  client WebSocket Deriv résilient (retry + backoff), **souscription temps
  réel** (`stream_candles`, reconnexion automatique), repository DB ↔ moteur
  SMC, commande `fetch_candles`
- ✅ **Scanner** (`apps/scanner`) — `ScannerService` orchestre
  market_data → DecisionEngine → persistance → notifications, commande
  `run_scan`, page de statut des données, tâches Celery prêtes
- ✅ **Signaux persistés** + vues réelles : Centre de Signaux (tableau
  filtrable + scan à la demande) et Dashboard (stats + graphique Chart.js Prix/RSI)
- ✅ **Authentification** (`apps/accounts`) — User + UserProfile (rôles
  ADMIN/TRADER/VIEWER), journal d'audit automatique (connexions,
  échecs, actions sensibles)
- ✅ **Risk Center réel** (`apps/risk`) — réglages de risque configurables,
  calculateur de lot size, protection du capital (arrêt automatique après
  3 pertes consécutives ou drawdown journalier > 20%)
- ✅ **Journal de trading** (`apps/journal`) — CRUD complet des trades,
  répercussion automatique sur l'état du compte à la clôture
- ✅ **Analytics** (`apps/analytics`) — win rate, profit factor, max
  drawdown, PnL net, courbe d'équité (Chart.js)
- ✅ **Notifications** (`apps/notifications`) — Dashboard + Telegram + Email,
  préférences par utilisateur et par type d'événement, câblées sur les
  nouveaux signaux et les alertes de risque
- ✅ **Paramètres** (`apps/settings_app`) — page centrale regroupant Risk
  Center, Notifications et sécurité du compte
- ✅ **78 tests automatisés, tous passants** (`python manage.py test`)

## Utilisation avec de vraies données Deriv

```bash
# 1. Renseigner DERIV_APP_ID (et DERIV_API_TOKEN si besoin) dans .env
#    -> créer une app sur https://developers.deriv.com

# 2. Créer un compte administrateur
python manage.py createsuperuser

# 3. Récupérer l'historique
python manage.py fetch_candles --all --count 500

# 4. Lancer un scan (génère, persiste et notifie un signal par instrument)
python manage.py run_scan

# 5. Voir le résultat
python manage.py runserver
# -> http://127.0.0.1:8000/               (dashboard + graphique)
# -> http://127.0.0.1:8000/signals/       (centre de signaux)
# -> http://127.0.0.1:8000/risk/          (calculateur de lot size)
# -> http://127.0.0.1:8000/journal/       (journal de trades)
# -> http://127.0.0.1:8000/analytics/     (win rate, équité)
# -> http://127.0.0.1:8000/notifications/ (préférences Telegram/Email)
```

### Flux temps réel (optionnel, en plus du polling périodique)

```bash
python manage.py stream_candles --instrument BOOM1000 --timeframe M1
```
Process longue durée à lancer séparément (systemd/supervisor en prod),
maintient une connexion WebSocket ouverte et sauvegarde chaque bougie
au fil de l'eau.

### Automatisation (Celery)

```bash
celery -A config worker -l info
celery -A config beat -l info   # une fois le beat_schedule décommenté dans config/celery.py
```

### Notifications Telegram

1. Créer un bot via [@BotFather](https://t.me/BotFather), récupérer le token
2. Renseigner `TELEGRAM_BOT_TOKEN` dans `.env`
3. Chaque utilisateur renseigne son `telegram_chat_id` (admin Django,
   section UserProfile, pour l'instant) et active Telegram dans
   `/notifications/`

## Prochaines pistes d'amélioration (facultatif)

1. Souscriptions temps réel multiples orchestrées en un seul process
   (actuellement : un process par instrument/timeframe)
2. Champ dédié pour éditer le `telegram_chat_id` directement depuis
   `/settings/` (actuellement via l'admin Django)
3. Tests de charge sur le scanner avant un usage en production
4. Déploiement (gunicorn + whitenoise déjà dans `requirements.txt`,
   configuration serveur à faire selon l'hébergeur choisi)

## Stratégie (rappel)

- **M30** : tendance / structure de marché
- **M15** : confirmation BOS/CHoCH/liquidité
- **M1** : confirmation RSI + timing d'entrée
- Risque par défaut : 1% (configurable 0.5/1/2%), RR minimum 1:2,
  max 2 positions par setup, arrêt après 3 pertes consécutives ou
  drawdown journalier > 20%.
