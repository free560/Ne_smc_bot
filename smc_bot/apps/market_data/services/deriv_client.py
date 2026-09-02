"""
apps/market_data/services/deriv_client.py

Client WebSocket pour l'API Deriv (https://developers.deriv.com).
Utilisé pour récupérer l'historique de bougies OHLC (candles) des
instruments synthétiques Boom 1000 / Crash 1000.

Conçu pour être résilient : retry avec backoff exponentiel, timeouts
explicites, erreurs typées. Vu les soucis DNS/réseau déjà rencontrés
sous Windows, chaque échec est loggé avec un message exploitable plutôt
que de laisser une exception websockets brute remonter.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import logging
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger("apps.market_data")

# Granularités Deriv en secondes
GRANULARITY_M1 = 60
GRANULARITY_M15 = 900
GRANULARITY_M30 = 1800

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 2

# Deriv sert son WebSocket derrière Cloudflare, qui rejette avec HTTP 401
# les connexions qui n'ont pas l'air de venir d'un navigateur (pas d'Origin,
# User-Agent non reconnu). On imite un client web légitime pour passer
# cette couche de protection - ça n'a rien à voir avec l'authentification
# Deriv elle-même (app_id / token), qui se négocie après la poignée de main.
#
# On passe ces informations comme de simples en-têtes HTTP (via
# `additional_headers` ou `extra_headers` selon la version de la librairie
# `websockets` installée) plutôt que par les raccourcis `origin=` /
# `user_agent_header=` : ces raccourcis existent dans la signature de
# `connect()` sur presque toutes les versions, mais certaines versions
# basculent en interne sur une implémentation "legacy" qui ne les gère
# pas et les laisse fuiter jusqu'à `create_connection()`, provoquant un
# TypeError. Les en-têtes bruts, eux, sont gérés de façon stable partout.
DERIV_ORIGIN = "https://app.deriv.com"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _browser_like_connect_kwargs() -> dict[str, Any]:
    """
    Détecte, via la signature de `websockets.connect`, quel nom de
    paramètre utiliser pour passer des en-têtes HTTP additionnels
    (`additional_headers` sur les versions récentes, `extra_headers`
    sur les plus anciennes), et renvoie le kwarg correspondant.
    """
    headers = {"Origin": DERIV_ORIGIN, "User-Agent": BROWSER_USER_AGENT}
    params = inspect.signature(websockets.connect).parameters

    if "additional_headers" in params:
        return {"additional_headers": headers}
    if "extra_headers" in params:
        return {"extra_headers": headers}
    return {}  # version inconnue sans support d'en-têtes - on se connecte sans


def _build_ws_url(ws_url: str, app_id: str) -> str:
    """
    Construit l'URL de connexion finale selon le type d'endpoint Deriv :
      - Legacy (ws.derivws.com/websockets/v3) : l'app_id est un paramètre
        de requête OBLIGATOIRE -> "?app_id=<id>".
      - Nouvelle Options API, endpoint public (api.derivws.com/trading/v1/
        options/ws/public) : AUCUN app_id n'est attendu dans l'URL - la
        connexion se fait directement, sans authentification ni identifiant.
        Ajouter "?app_id=" ici serait incorrect et pourrait faire échouer
        la connexion.
    """
    if "ws.derivws.com" in ws_url:
        return f"{ws_url}?app_id={app_id}"
    return ws_url


class DerivConnectionError(Exception):
    """Levée quand la connexion WebSocket à Deriv échoue après tous les retries."""


class DerivAPIError(Exception):
    """Levée quand Deriv répond avec un objet 'error' dans le payload JSON."""


@dataclass(frozen=True)
class RawCandle:
    epoch: int
    open: float
    high: float
    low: float
    close: float


class DerivClient:
    """
    Client minimal, sans état persistant entre les appels : chaque
    `fetch_candles` ouvre sa propre connexion, envoie une requête,
    récupère la réponse, puis ferme proprement la connexion.

    Pour un usage haute fréquence (scanner temps réel), préférer une
    connexion persistante avec `connect()` / `close()` explicites
    (voir `open_session` en Phase suivante si besoin de souscriptions
    temps réel via `subscribe`).
    """

    def __init__(
        self,
        app_id: str,
        api_token: str = "",
        ws_url: str = "wss://ws.derivws.com/websockets/v3",
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        if "ws.derivws.com" in ws_url and not app_id:
            raise ValueError("DERIV_APP_ID est requis pour l'endpoint legacy ws.derivws.com (voir .env)")
        self.app_id = app_id
        self.api_token = api_token
        self.ws_url = _build_ws_url(ws_url, app_id)
        self.timeout = timeout
        self.max_retries = max_retries
        self._req_id_counter = itertools.count(1)

    # ------------------------------------------------------------------
    # BAS NIVEAU : une requête = une connexion (avec retry)
    # ------------------------------------------------------------------
    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        req_id = next(self._req_id_counter)
        payload = {**payload, "req_id": req_id}

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with websockets.connect(
                    self.ws_url,
                    open_timeout=self.timeout,
                    close_timeout=5,
                    **_browser_like_connect_kwargs(),
                ) as ws:
                    if self.api_token:
                        await ws.send(json.dumps({"authorize": self.api_token, "req_id": req_id}))
                        auth_raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                        auth_response = json.loads(auth_raw)
                        if "error" in auth_response:
                            raise DerivAPIError(
                                f"Échec d'authentification Deriv : {auth_response['error'].get('message')}"
                            )

                    await ws.send(json.dumps(payload))
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    response = json.loads(raw)

                    if "error" in response:
                        raise DerivAPIError(response["error"].get("message", "Erreur Deriv inconnue"))

                    return response

            except (WebSocketException, OSError, asyncio.TimeoutError) as exc:
                last_error = exc
                wait_s = DEFAULT_BACKOFF_BASE_SECONDS * attempt
                logger.warning(
                    "Deriv WS - tentative %s/%s échouée (%s). Nouvelle tentative dans %ss.",
                    attempt, self.max_retries, exc, wait_s,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait_s)

        raise DerivConnectionError(
            f"Impossible de joindre Deriv après {self.max_retries} tentatives : {last_error}. "
            "Vérifie ta connexion réseau / résolution DNS de ws.derivws.com."
        )

    # ------------------------------------------------------------------
    # HISTORIQUE DE BOUGIES
    # ------------------------------------------------------------------
    async def fetch_candles_async(
        self, symbol: str, granularity: int, count: int = 500
    ) -> list[RawCandle]:
        payload = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": "candles",
            "granularity": granularity,
        }
        response = await self._request(payload)
        raw_candles = response.get("candles", [])

        return [
            RawCandle(
                epoch=int(c["epoch"]),
                open=float(c["open"]),
                high=float(c["high"]),
                low=float(c["low"]),
                close=float(c["close"]),
            )
            for c in raw_candles
        ]

    def fetch_candles(self, symbol: str, granularity: int, count: int = 500) -> list[RawCandle]:
        """Wrapper synchrone, pratique pour les vues Django / tâches Celery."""
        return asyncio.run(self.fetch_candles_async(symbol, granularity, count))