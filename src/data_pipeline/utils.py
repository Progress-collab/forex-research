from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Callable, Iterable, Mapping, MutableMapping


def _hash_key(parts: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
    return digest.hexdigest()


@dataclass(slots=True)
class FileCache:
    """
    Простейший файловый кэш для JSON-совместимых ответов API.
    """

    cache_dir: Path
    ttl_seconds: int = 900

    def __post_init__(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, namespace: str, params: Mapping[str, Any]) -> MutableMapping[str, Any] | None:
        key = _hash_key([namespace, json.dumps(params, sort_keys=True, ensure_ascii=False)])
        path = self._cache_path(key)
        if not path.exists():
            return None
        if time() - path.stat().st_mtime > self.ttl_seconds:
            path.unlink(missing_ok=True)
            return None
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def set(self, namespace: str, params: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        key = _hash_key([namespace, json.dumps(params, sort_keys=True, ensure_ascii=False)])
        path = self._cache_path(key)
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)


def batched(iterable: Iterable[Any], batch_size: int) -> Iterable[list[Any]]:
    """
    Итератор пачек фиксированного размера.
    """

    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def safe_get(dct: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Безопасное извлечение вложенных ключей.
    """

    current: Any = dct
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current

