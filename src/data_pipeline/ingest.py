from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Mapping, MutableMapping, Sequence

from .config import DataPipelineConfig
from .moex_client import MoexClient, filter_fx_pairs
from .storage import save_metadata_report, save_raw_candles
from .validation import (
    ValidationError,
    build_validation_summary,
    check_duplicates,
    require_non_empty,
    validate_candle_schema,
    validate_chronology,
)


log = logging.getLogger(__name__)


def ingest_instrument_history(
    config: DataPipelineConfig,
    secid: str,
    interval: int = 24,
    start: datetime | None = None,
    end: datetime | None = None,
) -> MutableMapping[str, object]:
    """
    Загрузка и проверка исторических свечей выбранного инструмента.
    """

    client = MoexClient(config)

    metadata = client.fetch_marketdata(secid)
    save_metadata_report(config, secid, metadata)

    candles = client.fetch_candles(secid, interval=interval, start=start, end=end)

    errors: list[str] = []
    try:
        require_non_empty(candles, context=f"{secid}:{interval}")
        validate_candle_schema(candles)
        check_duplicates(candles)
        validate_chronology(candles)
    except ValidationError as exc:
        errors.append(str(exc))
        log.exception("Ошибка валидации данных %s", secid)

    save_raw_candles(config, secid, interval, candles)

    return build_validation_summary(secid=secid, candles_count=len(candles), errors=errors)


def list_fx_instruments(config: DataPipelineConfig) -> Sequence[Mapping[str, object]]:
    client = MoexClient(config)
    securities = client.list_currencies()
    return filter_fx_pairs(securities)


def bulk_ingest(
    config: DataPipelineConfig,
    secids: Iterable[str],
    interval: int = 24,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Sequence[MutableMapping[str, object]]:
    reports = []
    for secid in secids:
        report = ingest_instrument_history(
            config=config,
            secid=secid,
            interval=interval,
            start=start,
            end=end,
        )
        reports.append(report)
    return reports

