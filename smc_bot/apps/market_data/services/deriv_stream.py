"""
apps/market_data/services/deriv_stream.py

Flux temps réel des bougies Deriv.

Connexion WebSocket persistante :
    python manage.py stream_candles --instrument BOOM1000 --timeframe M1

Le serveur Deriv envoie :
1. un snapshot initial dans "candles"
2. ensuite des mises à jour dans "ohlc"

Le flux est automatiquement reconnecté en cas de coupure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

import websockets
from websockets.exceptions import WebSocketException

from apps.market_data.services.deriv_client import RawCandle, _browser_like_connect_kwargs, _build_ws_url

logger = logging.getLogger("apps.market_data")

CandleCallback = Callable[[RawCandle], Awaitable[None]]

RECONNECT_BASE_DELAY_SECONDS = 3
RECONNECT_MAX_DELAY_SECONDS = 60


class DerivStream:

    def __init__(self, app_id: str, ws_url: str = "wss://ws.derivws.com/websockets/v3"):
        if "ws.derivws.com" in ws_url and not app_id:
            raise ValueError("DERIV_APP_ID est requis pour l'endpoint legacy ws.derivws.com")
        self.ws_url = _build_ws_url(ws_url, app_id)
        self._stop = False

    def stop(self) -> None:
        """Demande l'arrêt propre du flux."""
        self._stop = True

    async def run(
        self,
        symbol: str,
        granularity: int,
        on_candle: CandleCallback,
    ) -> None:

        delay = RECONNECT_BASE_DELAY_SECONDS

        logger.info(
            "Démarrage DerivStream : symbol=%s granularity=%s",
            symbol,
            granularity,
        )

        while not self._stop:

            try:

                await self._connect_and_stream(
                    symbol=symbol,
                    granularity=granularity,
                    on_candle=on_candle,
                )

                # Si la connexion se termine normalement,
                # on repart avec le délai minimum.
                delay = RECONNECT_BASE_DELAY_SECONDS

                if not self._stop:
                    logger.warning(
                        "Connexion Deriv fermée. Reconnexion dans %s secondes...",
                        delay,
                    )

                    await asyncio.sleep(delay)

            except (
                WebSocketException,
                OSError,
                asyncio.TimeoutError,
                json.JSONDecodeError,
            ) as exc:

                if self._stop:
                    break

                logger.exception(
                    "Erreur dans le flux Deriv : %s",
                    exc,
                )

                logger.warning(
                    "Nouvelle tentative dans %s secondes...",
                    delay,
                )

                await asyncio.sleep(delay)

                delay = min(
                    delay * 2,
                    RECONNECT_MAX_DELAY_SECONDS,
                )

            except Exception as exc:

                # Très important :
                # une erreur inattendue ne doit pas tuer définitivement
                # le bot.
                if self._stop:
                    break

                logger.exception(
                    "Erreur inattendue dans DerivStream : %s",
                    exc,
                )

                await asyncio.sleep(delay)

                delay = min(
                    delay * 2,
                    RECONNECT_MAX_DELAY_SECONDS,
                )

    async def _connect_and_stream(
        self,
        symbol: str,
        granularity: int,
        on_candle: CandleCallback,
    ) -> None:

        logger.info(
            "Connexion à Deriv : %s",
            self.ws_url,
        )

        async with websockets.connect(
            self.ws_url,
            open_timeout=15,
            close_timeout=5,
            ping_interval=20,
            ping_timeout=20,
            **_browser_like_connect_kwargs(),
        ) as ws:

            logger.info(
                "WebSocket Deriv connecté pour %s M%s",
                symbol,
                granularity,
            )

            payload = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 1,
                "end": "latest",
                "start": 1,
                "style": "candles",
                "granularity": granularity,
                "subscribe": 1,
            }

            logger.info(
                "Souscription Deriv : %s",
                json.dumps(payload),
            )

            await ws.send(json.dumps(payload))

            logger.info(
                "Souscription envoyée. En attente des bougies..."
            )

            async for raw_message in ws:

                if self._stop:
                    logger.info("Arrêt demandé du flux Deriv.")
                    break

                try:
                    message = json.loads(raw_message)

                except json.JSONDecodeError:
                    logger.warning(
                        "Message JSON invalide reçu de Deriv : %s",
                        raw_message,
                    )
                    continue

                # --------------------------------------------------
                # ERREUR DERIV
                # --------------------------------------------------

                if "error" in message:

                    error = message["error"]

                    logger.error(
                        "Erreur Deriv : %s",
                        error,
                    )

                    # Une erreur de souscription doit provoquer
                    # une reconnexion plutôt que continuer dans le vide.
                    raise WebSocketException(
                        f"Deriv API error: {error}"
                    )

                msg_type = message.get("msg_type")

                logger.debug(
                    "Message Deriv reçu : msg_type=%s",
                    msg_type,
                )

                # --------------------------------------------------
                # SUBSCRIPTION
                # --------------------------------------------------

                if "subscription" in message:

                    subscription = message["subscription"]

                    logger.info(
                        "Abonnement Deriv actif : %s",
                        subscription,
                    )

                # --------------------------------------------------
                # BOUGIE
                # --------------------------------------------------

                candle = self._parse_message(message)

                if candle is None:
                    continue

                logger.debug(
                    "Bougie reçue : epoch=%s O=%s H=%s L=%s C=%s",
                    candle.epoch,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                )

                try:

                    await on_candle(candle)

                except Exception as exc:

                    # Une erreur DB/scanner ne doit PAS tuer
                    # la connexion WebSocket.
                    logger.exception(
                        "Erreur traitement bougie epoch=%s : %s",
                        candle.epoch,
                        exc,
                    )

    @staticmethod
    def _parse_message(
        message: dict,
    ) -> RawCandle | None:

        # ----------------------------------------------------------
        # MISE À JOUR TEMPS RÉEL
        # ----------------------------------------------------------

        ohlc = message.get("ohlc")

        if ohlc:

            try:

                return RawCandle(
                    epoch=int(ohlc["open_time"]),
                    open=float(ohlc["open"]),
                    high=float(ohlc["high"]),
                    low=float(ohlc["low"]),
                    close=float(ohlc["close"]),
                )

            except (KeyError, TypeError, ValueError) as exc:

                logger.warning(
                    "OHLC Deriv invalide : %s | erreur=%s",
                    ohlc,
                    exc,
                )

                return None

        # ----------------------------------------------------------
        # SNAPSHOT INITIAL
        # ----------------------------------------------------------

        candles = message.get("candles")

        if candles:

            try:

                last = candles[-1]

                return RawCandle(
                    epoch=int(last["epoch"]),
                    open=float(last["open"]),
                    high=float(last["high"]),
                    low=float(last["low"]),
                    close=float(last["close"]),
                )

            except (KeyError, TypeError, ValueError) as exc:

                logger.warning(
                    "Bougie initiale Deriv invalide : %s | erreur=%s",
                    candles[-1] if candles else None,
                    exc,
                )

                return None

        return None

        print(json.dumps(message, indent=2))

