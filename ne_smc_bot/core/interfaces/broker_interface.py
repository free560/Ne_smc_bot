from abc import ABC, abstractmethod


class BrokerInterface(ABC):
    """Contrat que tout adapter broker doit respecter."""

    @abstractmethod
    def connect(self):
        ...

    @abstractmethod
    def disconnect(self):
        ...

    @abstractmethod
    def get_balance(self) -> float:
        ...

    @abstractmethod
    def get_market_data(self, symbol: str, timeframe: str, count: int) -> list[dict]:
        """Retourne une liste de bougies : [{timestamp, open, high, low, close, volume}, ...]"""
        ...

    @abstractmethod
    def place_order(self, symbol: str, direction: str, lot_size: float, stop_loss: float, take_profit: float):
        ...