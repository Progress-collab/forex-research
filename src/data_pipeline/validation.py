from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable, Mapping, MutableMapping, Sequence


class ValidationError(Exception):
    pass


def require_non_empty(rows: Sequence[Mapping[str, object]], context: str) -> None:
    if not rows:
        raise ValidationError(f"Нет данных в выборке: {context}")


def validate_candle_schema(rows: Iterable[Mapping[str, object]]) -> None:
    required_fields = {"open", "close", "high", "low", "volume", "begin", "end"}
    for idx, row in enumerate(rows):
        missing = required_fields - row.keys()
        if missing:
            raise ValidationError(f"В строке {idx} отсутствуют поля: {missing}")


def validate_chronology(rows: Iterable[Mapping[str, object]]) -> None:
    prev_end: datetime | None = None
    for idx, row in enumerate(rows):
        end_value = row.get("end")
        if isinstance(end_value, str):
            end_dt = datetime.fromisoformat(end_value)
        elif isinstance(end_value, datetime):
            end_dt = end_value
        else:
            raise ValidationError(f"Поле end имеет неподдерживаемый тип: {type(end_value)}")

        if prev_end and end_dt < prev_end:
            raise ValidationError(f"Нарушена хронология на строке {idx}")
        prev_end = end_dt


def check_duplicates(rows: Sequence[Mapping[str, object]], key: str = "end") -> None:
    counter = Counter(row.get(key) for row in rows)
    dup = {value: count for value, count in counter.items() if value and count > 1}
    if dup:
        raise ValidationError(f"Найдены дубликаты по ключу {key}: {dup}")


def build_validation_summary(
    secid: str,
    candles_count: int,
    errors: Sequence[str],
) -> MutableMapping[str, object]:
    return {
        "secid": secid,
        "candles_count": candles_count,
        "errors": list(errors),
    }

