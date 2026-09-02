import asyncio
import json
import requests
import websockets
from decouple import config
from core.interfaces.broker_interface import BrokerInterface

REST_BASE = "https://api.derivws.com/trading/v1/options"
PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


class DerivAdapter(BrokerInterface):
    def __init__(self, api_token: str = None, app_id: str = None, account_id: str = None, account_type: str = None):
        self.token = api_token
        self.app_id = app_id or config('DERIV_APP_ID')
        self.account_id = account_id
        self.account_type = account_type
        self.connection = None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Deriv-App-ID": self.app_id,
            "Content-Type": "application/json",
        }

    def get_accounts(self) -> list[dict]:
        resp = requests.get(f"{REST_BASE}/accounts", headers=self._headers())
        resp.raise_for_status()
        return resp.json()["data"]

    def _resolve_account_id(self, prefer_type: str = None):
        if self.account_id:
            return self.account_id

        accounts = self.get_accounts()
        if not accounts:
            raise ValueError("Aucun compte Deriv trouvé pour ce token")

        if prefer_type:
            matching = [a for a in accounts if a.get('account_type') == prefer_type]
            if matching:
                self.account_id = matching[0]['account_id']
                return self.account_id

        self.account_id = accounts[0]['account_id']
        return self.account_id


    def _get_authenticated_ws_url(self) -> str:
        account_id = self._resolve_account_id(prefer_type=self.account_type)
        resp = requests.post(f"{REST_BASE}/accounts/{account_id}/otp", headers=self._headers())
        resp.raise_for_status()
        return resp.json()["data"]["url"]

    async def _connect_ws(self):
        ws_url = self._get_authenticated_ws_url()  # OTP à usage court, récupéré à chaque connexion
        self.connection = await websockets.connect(ws_url)

    def connect(self):
        asyncio.run(self._connect_ws())

    def disconnect(self):
        if self.connection:
            asyncio.run(self.connection.close())

    def get_balance(self) -> float:
        async def _balance():
            await self._connect_ws()
            await self.connection.send(json.dumps({"balance": 1}))
            response = json.loads(await self.connection.recv())
            if 'error' in response:
                raise ConnectionError(f"Erreur Deriv : {response['error']['message']}")
            return response['balance']['balance']
        return asyncio.run(_balance())

    def get_market_data(self, symbol: str, timeframe: str, count: int = 100) -> list[dict]:
        """Les données de marché sont publiques — aucune authentification nécessaire."""
        granularity_map = {'M5': 300, 'M15': 900, 'H1': 3600, 'H4': 14400, 'D1': 86400}

        async def _fetch():
            ws = await websockets.connect(PUBLIC_WS_URL)
            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "granularity": granularity_map[timeframe],
                "style": "candles",
            }
            await ws.send(json.dumps(request))
            response = json.loads(await ws.recv())
            await ws.close()
            if 'error' in response:
                raise ConnectionError(f"Erreur Deriv : {response['error']['message']}")
            candles = response.get('candles', [])
            return [
                {'timestamp': c['epoch'], 'open': c['open'], 'high': c['high'],
                 'low': c['low'], 'close': c['close'], 'volume': 0}
                for c in candles
            ]
        return asyncio.run(_fetch())

    def place_order(self, symbol, direction, lot_size, stop_loss, take_profit, entry_price=None, multiplier=100):
        if entry_price is None:
            raise ValueError("entry_price est requis pour calculer le stake et les montants SL/TP")

        stake = round(float(lot_size) * 1000, 2)
        stop_distance_pct = abs(entry_price - stop_loss) / entry_price
        target_distance_pct = abs(take_profit - entry_price) / entry_price
        monetary_stop_loss = round(stake * multiplier * stop_distance_pct, 2)
        monetary_take_profit = round(stake * multiplier * target_distance_pct, 2)
        contract_type = 'MULTUP' if direction == 'buy' else 'MULTDOWN'

        async def _place():
            await self._connect_ws()

            proposal_request = {
                "proposal": 1, "amount": stake, "basis": "stake",
                "contract_type": contract_type, "currency": "USD", "symbol": symbol,
                "multiplier": multiplier,
                "limit_order": {"stop_loss": monetary_stop_loss, "take_profit": monetary_take_profit},
            }
            await self.connection.send(json.dumps(proposal_request))
            proposal_response = json.loads(await self.connection.recv())
            if 'error' in proposal_response:
                return {'success': False, 'error': proposal_response['error']['message']}

            proposal_id = proposal_response['proposal']['id']
            ask_price = proposal_response['proposal']['ask_price']

            await self.connection.send(json.dumps({"buy": proposal_id, "price": ask_price}))
            buy_response = json.loads(await self.connection.recv())
            if 'error' in buy_response:
                return {'success': False, 'error': buy_response['error']['message']}

            return {
                'success': True, 'contract_id': buy_response['buy']['contract_id'],
                'stake': stake, 'monetary_stop_loss': monetary_stop_loss,
                'monetary_take_profit': monetary_take_profit, 'buy_price': buy_response['buy']['buy_price'],
            }

        return asyncio.run(_place())