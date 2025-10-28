from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Order:
    order_id: int
    amount: float
