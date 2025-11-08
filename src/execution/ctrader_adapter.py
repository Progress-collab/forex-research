from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .models import ExecutionReport, Order


log = logging.getLogger(__name__)


@dataclass(slots=True)
class CTraderCredentials:
    client_id: str
    client_secret: str
    access_token: str
    account_id: str
    base_url: str = "https://api.ctrader.com"


class CTraderClient:
    """
    Упрощённый клиент для cTrader Open API (REST).
    Для production потребуется полноценная реализация OAuth и потоковой подписки.
    """

    def __init__(self, creds: CTraderCredentials):
        self.creds = creds

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.creds.access_token}",
            "Content-Type": "application/json",
        }

    def place_order(self, order: Order) -> ExecutionReport:
        payload = {
            "accountId": self.creds.account_id,
            "symbol": order.secid,
            "volume": order.quantity,
            "side": order.side,
            "type": order.order_type,
            "limitPrice": order.price,
        }
        url = f"{self.creds.base_url}/orders"
        resp = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=15)
        if resp.status_code >= 400:
            log.error("cTrader error: %s", resp.text)
            return ExecutionReport(
                order=order,
                status="rejected",
                executed_quantity=0.0,
                rejection_reason=resp.text,
            )
        data: Dict[str, Any] = resp.json()
        return ExecutionReport(
            order=order,
            status="accepted",
            executed_quantity=float(data.get("executedVolume", 0.0)),
            average_price=float(data.get("price", order.price or 0.0)),
            broker_payload=data,
        )

    def cancel_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.creds.base_url}/orders/{order_id}"
        resp = requests.delete(url, headers=self._headers(), timeout=15)
        if resp.status_code >= 400:
            log.error("cTrader cancel error: %s", resp.text)
            return None
        return resp.json()

