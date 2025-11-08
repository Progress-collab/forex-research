from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAAccountAuthRes,
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetAccountListByAccessTokenRes,
    ProtoOAGetTrendbarsReq,
    ProtoOAGetTrendbarsRes,
    ProtoOASubscribeSpotsRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
    ProtoOAUnsubscribeSpotsReq,
    ProtoOAUnsubscribeSpotsRes,
)
from twisted.internet import reactor

from .symbol_info import SymbolInfoCache


log = logging.getLogger(__name__)

TREND_BAR_PERIODS = {
    "m1": ProtoOATrendbarPeriod.M1,
    "m5": ProtoOATrendbarPeriod.M5,
    "m15": ProtoOATrendbarPeriod.M15,
    "m30": ProtoOATrendbarPeriod.M30,
    "h1": ProtoOATrendbarPeriod.H1,
    "h4": ProtoOATrendbarPeriod.H4,
    "d1": ProtoOATrendbarPeriod.D1,
}


@dataclass(slots=True)
class CTraderCredentials:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: Optional[str] = None
    environment: str = "live"  # live | demo


class CTraderTrendbarFetcher:
    """
    Минималистичный клиент для получения исторических баров из cTrader Open API.
    """

    def __init__(self, creds: CTraderCredentials, *, symbols: Optional[Iterable[str]] = None):
        self._creds = creds
        self._host = (
            EndPoints.PROTOBUF_LIVE_HOST if creds.environment == "live" else EndPoints.PROTOBUF_DEMO_HOST
        )
        self._port = EndPoints.PROTOBUF_PORT
        self._client: Optional[Client] = None
        self._client_thread: Optional[threading.Thread] = None
        self._connected = threading.Event()
        self._application_authed = threading.Event()
        self._account_ready = threading.Event()
        self._symbols_ready = threading.Event()
        self._shutdown = threading.Event()

        self._account_id: Optional[int] = None
        self._symbols_by_name: Dict[str, int] = {}
        self._requested_symbols = set(symbols or [])
        self._symbol_info_cache = SymbolInfoCache()

        self._pending_trendbars: Optional[Dict[str, object]] = None

        self._start_client()
        self._await_events()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def get_trendbars(
        self,
        symbol: str,
        period: str = "m15",
        *,
        bars: int = 500,
        to_time: Optional[datetime] = None,
    ) -> List[Dict[str, float]]:
        if period.lower() not in TREND_BAR_PERIODS:
            raise ValueError(f"Unsupported period '{period}'. Available: {list(TREND_BAR_PERIODS)}")
        if symbol not in self._symbols_by_name:
            log.info("Symbol %s not in cache, refreshing symbol list", symbol)
            self._request_symbols()
            self._symbols_ready.wait(timeout=10)
            if symbol not in self._symbols_by_name:
                raise ValueError(f"Symbol '{symbol}' not found in cTrader account instruments.")

        symbol_id = self._symbols_by_name[symbol]
        period_enum = TREND_BAR_PERIODS[period.lower()]

        to_dt = to_time or datetime.utcnow().replace(tzinfo=timezone.utc)
        duration_map = {
            ProtoOATrendbarPeriod.M1: timedelta(minutes=1),
            ProtoOATrendbarPeriod.M5: timedelta(minutes=5),
            ProtoOATrendbarPeriod.M15: timedelta(minutes=15),
            ProtoOATrendbarPeriod.M30: timedelta(minutes=30),
            ProtoOATrendbarPeriod.H1: timedelta(hours=1),
            ProtoOATrendbarPeriod.H4: timedelta(hours=4),
            ProtoOATrendbarPeriod.D1: timedelta(days=1),
        }
        delta = duration_map[period_enum] * bars
        from_dt = to_dt - delta

        request = ProtoOAGetTrendbarsReq()
        request.payloadType = ProtoOAGetTrendbarsReq().payloadType
        request.ctidTraderAccountId = self._account_id
        request.symbolId = symbol_id
        request.period = period_enum
        request.fromTimestamp = int(from_dt.timestamp() * 1000)
        request.toTimestamp = int(to_dt.timestamp() * 1000)
        pending = {"event": threading.Event(), "result": None, "error": None}
        self._pending_trendbars = pending

        deferred = self._client.send(request)
        deferred.addErrback(self._on_error)

        event = pending["event"]
        event.wait(timeout=20)

        if pending.get("error"):
            raise RuntimeError(f"cTrader trendbars error: {pending['error']}")

        result = pending.get("result")
        if result is None:
            raise RuntimeError("Timeout waiting for cTrader trendbars response.")

        return result

    def close(self) -> None:
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        # Сохраняем информацию о символах перед закрытием
        try:
            self._symbol_info_cache.save()
        except Exception as e:  # noqa: BLE001
            log.warning("Failed to save symbol info cache: %s", e)

        def stop_reactor():
            if reactor.running:
                reactor.stop()

        reactor.callFromThread(stop_reactor)
        if self._client:
            try:
                self._client.stopService()
            except Exception:  # noqa: BLE001
                pass
        if self._client_thread and self._client_thread.is_alive():
            self._client_thread.join(timeout=5)

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _start_client(self) -> None:
        self._client = Client(self._host, self._port, TcpProtocol)
        self._client.setConnectedCallback(self._on_connected)
        self._client.setDisconnectedCallback(self._on_disconnected)
        self._client.setMessageReceivedCallback(self._on_message)

        def run_client():
            try:
                self._client.startService()
                reactor.run(installSignalHandlers=False)
            except Exception as exc:  # noqa: BLE001
                log.error("Failed to start cTrader client: %s", exc)
                self._connected.clear()

        self._client_thread = threading.Thread(target=run_client, daemon=True)
        self._client_thread.start()

    def _await_events(self) -> None:
        if not self._connected.wait(timeout=10):
            raise RuntimeError("Timed out waiting for cTrader connection.")
        if not self._application_authed.wait(timeout=10):
            raise RuntimeError("Timed out waiting for application authentication.")
        if not self._account_ready.wait(timeout=15):
            raise RuntimeError("Timed out waiting for account authentication.")
        if not self._symbols_ready.wait(timeout=15):
            log.warning("Symbols were not loaded within timeout; will fetch on demand.")

    # ------------------------------------------------------------------ #
    # Callbacks
    # ------------------------------------------------------------------ #
    def _on_connected(self, client: Client) -> None:
        log.info("Connected to cTrader (%s)", self._creds.environment)
        self._connected.set()
        request = ProtoOAApplicationAuthReq()
        request.clientId = self._creds.client_id
        request.clientSecret = self._creds.client_secret
        deferred = client.send(request)
        deferred.addErrback(self._on_error)

    def _on_disconnected(self, client: Client, reason: str) -> None:
        log.warning("Disconnected from cTrader: %s", reason)
        self._connected.clear()
        if not self._shutdown.is_set():
            time.sleep(5)
            self._start_client()

    def _on_message(self, client: Client, message) -> None:  # noqa: ANN001
        payload_type = message.payloadType
        if payload_type == ProtoOAApplicationAuthRes().payloadType:
            self._handle_application_auth(message)
        elif payload_type == ProtoOAGetAccountListByAccessTokenRes().payloadType:
            self._handle_account_list(message)
        elif payload_type == ProtoOAAccountAuthRes().payloadType:
            self._handle_account_auth(message)
        elif payload_type == ProtoOASymbolsListRes().payloadType:
            self._handle_symbols_list(message)
        elif payload_type == ProtoOAGetTrendbarsRes().payloadType:
            self._handle_trendbars(message)
        elif payload_type in (
            ProtoOASubscribeSpotsRes().payloadType,
            ProtoOAUnsubscribeSpotsRes().payloadType,
        ):
            # ignore subscription responses for this fetcher
            return
        else:
            extracted = Protobuf.extract(message)
            log.debug("Unhandled message type %s: %s", payload_type, extracted)

    def _on_error(self, failure) -> None:  # noqa: ANN001
        log.error("cTrader API error: %s", failure)

    # ------------------------------------------------------------------ #
    # Message Handlers
    # ------------------------------------------------------------------ #
    def _handle_application_auth(self, message) -> None:  # noqa: ANN001
        log.info("Application authenticated.")
        self._application_authed.set()
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self._creds.access_token
        deferred = self._client.send(request)
        deferred.addErrback(self._on_error)

    def _handle_account_list(self, message) -> None:  # noqa: ANN001
        extracted = Protobuf.extract(message)
        accounts = extracted.ctidTraderAccount
        log.info("Received %s accounts from cTrader.", len(accounts))
        if not accounts:
            log.error("No cTrader accounts available for provided access token.")
            raise RuntimeError("No cTrader accounts available for provided access token.")

        account = next(iter(accounts))
        self._account_id = account.ctidTraderAccountId
        account_type = getattr(account, "accountType", "unknown")
        log.info("Selected account %s (type=%s)", self._account_id, account_type)

        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = self._account_id
        request.accessToken = self._creds.access_token
        deferred = self._client.send(request)
        deferred.addErrback(self._on_error)

    def _handle_account_auth(self, message) -> None:  # noqa: ANN001
        log.info("Account authenticated (%s).", self._account_id)
        self._account_ready.set()
        self._request_symbols()

    def _request_symbols(self) -> None:
        if not self._account_id:
            return
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self._account_id
        deferred = self._client.send(request)
        deferred.addErrback(self._on_error)

    def _handle_symbols_list(self, message) -> None:  # noqa: ANN001
        extracted = Protobuf.extract(message)
        symbols = extracted.symbol
        mapping = {symbol.symbolName: symbol.symbolId for symbol in symbols}
        self._symbols_by_name.update(mapping)
        log.info("Fetched %s symbols from cTrader.", len(symbols))
        # Сохраняем информацию о символах (swaps, комиссии и т.д.)
        self._symbol_info_cache.update_from_proto(symbols)
        self._symbols_ready.set()

    def _handle_trendbars(self, message) -> None:  # noqa: ANN001
        extracted = Protobuf.extract(message)
        trendbars = extracted.trendbar
        result = []
        for bar in trendbars:
            low_price = bar.low / 100000.0
            open_price = (bar.low + getattr(bar, "deltaOpen", 0)) / 100000.0
            close_price = (bar.low + getattr(bar, "deltaClose", 0)) / 100000.0
            high_price = (bar.low + getattr(bar, "deltaHigh", 0)) / 100000.0
            timestamp_minutes = getattr(bar, "utcTimestampInMinutes", 0)
            utc_ts = datetime.fromtimestamp(timestamp_minutes * 60, tz=timezone.utc)

            result.append(
                {
                    "open": open_price,
                    "close": close_price,
                    "high": high_price,
                    "low": low_price,
                    "volume": bar.volume,
                    "utc_time": utc_ts.isoformat(),
                }
            )

        if self._pending_trendbars:
            pending = self._pending_trendbars
            pending["result"] = result
            pending["event"].set()
            self._pending_trendbars = None
        else:
            log.warning("Received trendbars without matching request id.")


__all__ = ["CTraderCredentials", "CTraderTrendbarFetcher"]

