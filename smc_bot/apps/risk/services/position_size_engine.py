"""
apps/risk/services/position_size_engine.py

POSITION SIZE ENGINE
----------------------
Calcule la taille de position (lot size) recommandée à partir de :
  - le solde du compte
  - le risque accepté (%)
  - la distance jusqu'au Stop Loss

Priorité absolue : préservation du capital. En cas de paramètre invalide
(distance de SL nulle, solde nul...), l'engine renvoie 0 plutôt que de
risquer une division par zéro ou un lot aberrant.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizeResult:
    lot_size: float
    risk_amount: float
    stop_loss_distance: float
    warning: str | None = None


class PositionSizeEngine:
    def __init__(self, pip_value_per_lot: float = 1.0, min_lot: float = 0.01, lot_step: float = 0.01):
        """
        pip_value_per_lot : valeur monétaire d'un point de prix pour 1 lot
            (dépend du contrat de l'instrument - à ajuster selon les specs
            Deriv réelles de BOOM1000/CRASH1000 une fois connues).
        """
        self.pip_value_per_lot = pip_value_per_lot
        self.min_lot = min_lot
        self.lot_step = lot_step

    def calculate(self, balance: float, risk_percent: float, entry: float, stop_loss: float) -> PositionSizeResult:
        stop_loss_distance = abs(entry - stop_loss)

        if balance <= 0:
            return PositionSizeResult(0.0, 0.0, stop_loss_distance, warning="Solde du compte nul ou négatif")
        if stop_loss_distance <= 0:
            return PositionSizeResult(0.0, 0.0, stop_loss_distance, warning="Distance de Stop Loss nulle")

        risk_amount = balance * (risk_percent / 100)
        raw_lot = risk_amount / (stop_loss_distance * self.pip_value_per_lot)

        # Arrondi au pas de lot le plus proche, jamais en dessous du minimum
        rounded_lot = max(self.min_lot, round(raw_lot / self.lot_step) * self.lot_step)
        rounded_lot = round(rounded_lot, 2)

        return PositionSizeResult(
            lot_size=rounded_lot,
            risk_amount=round(risk_amount, 2),
            stop_loss_distance=round(stop_loss_distance, 5),
        )
