from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping

import requests

from .config import ApiCacheConfig, DataPipelineConfig
from .utils import FileCache, safe_get


log = logging.getLogger(__name__)

BASE_URL = "https://iss.moex.com/iss"


class MoexClient:
    """
    Клиент для ISS API Московской биржи с файловым кэшем.
    """

    def __init__(self, config: DataPipelineConfig):
        self._config = config
        self._cache = FileCache(
            config.api_cache.cache_dir, ttl_seconds=config.api_cache.ttl_seconds
        )

    def _request(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        cache_namespace: str | None = None,
        use_cache: bool = True,
    ) -> MutableMapping[str, Any]:
        params = dict(params or {})
        if use_cache and cache_namespace:
            cached = self._cache.get(cache_namespace, params)
            if cached is not None:
                return cached

        url = f"{BASE_URL}/{endpoint}"
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        payload: MutableMapping[str, Any] = resp.json()
        if use_cache and cache_namespace:
            self._cache.set(cache_namespace, params, payload)
        return payload

    # ---- Метаданные -----------------------------------------------------

    def list_currencies(self) -> List[Dict[str, Any]]:
        endpoint = f"engines/{self._config.engine}/markets/{self._config.board.lower()}/securities.json"
        payload = self._request(
            endpoint,
            params={"iss.meta": "off", "iss.only": "securities"},
            cache_namespace="securities:list",
        )
        columns = safe_get(payload, "securities", "columns", default=[])
        data = safe_get(payload, "securities", "data", default=[])
        return [dict(zip(columns, row)) for row in data]

    def get_security(self, secid: str) -> Dict[str, Any] | None:
        securities = self.list_currencies()
        for item in securities:
            if item.get("SECID") == secid:
                return item
        return None

    # ---- Исторические данные -------------------------------------------

    def fetch_candles(
        self,
        secid: str,
        interval: int = 24,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> List[Dict[str, Any]]:
        endpoint = f"engines/{self._config.engine}/markets/{self._config.board.lower()}/securities/{secid}/candles.json"
        params: Dict[str, Any] = {"iss.meta": "off", "interval": interval, "limit": 5000}
        if start:
            params["from"] = start.strftime("%Y-%m-%d")
        if end:
            params["till"] = end.strftime("%Y-%m-%d")

        payload = self._request(
            endpoint,
            params=params,
            cache_namespace=f"candles:{secid}:{interval}",
        )
        columns = safe_get(payload, "candles", "columns", default=[])
        data = safe_get(payload, "candles", "data", default=[])
        return [dict(zip(columns, row)) for row in data]

    def fetch_marketdata(self, secid: str) -> Dict[str, Any]:
        endpoint = f"engines/{self._config.engine}/markets/{self._config.board.lower()}/securities/{secid}.json"
        payload = self._request(
            endpoint,
            params={"iss.meta": "off"},
            cache_namespace=f"marketdata:{secid}",
        )
        return payload


def filter_fx_pairs(securities: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """
    Фильтр валютных инструментов по биржевым кодам.
    """

    relevant = []
    for item in securities:
        if item.get("SECID", "").startswith("USD") or item.get("SECNAME", "").startswith("US DOLLAR"):
            relevant.append(dict(item))
        elif item.get("SECID", "").startswith("EUR"):
            relevant.append(dict(item))
        elif "RUB" in item.get("SECID", ""):
            relevant.append(dict(item))
    return relevant

