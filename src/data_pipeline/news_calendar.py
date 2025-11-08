from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)


@dataclass(slots=True)
class EconomicEvent:
    """Структура события экономического календаря."""

    event_id: str
    country: str
    event_name: str
    importance: str  # high, medium, low
    timestamp: datetime
    currency: str
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    source: str = "tradingeconomics"


class TradingEconomicsAdapter:
    """Адаптер для TradingEconomics API."""

    BASE_URL = "https://api.tradingeconomics.com/calendar"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TRADINGECONOMICS_API_KEY")
        if not self.api_key:
            log.warning("TRADINGECONOMICS_API_KEY не установлен. Используйте переменную окружения.")

    def fetch_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        countries: Optional[List[str]] = None,
    ) -> List[EconomicEvent]:
        """
        Получает события из TradingEconomics API.
        
        Args:
            start_date: Начальная дата (по умолчанию сегодня)
            end_date: Конечная дата (по умолчанию через месяц)
            countries: Список стран (например, ['US', 'EU', 'GB', 'JP'])
        """
        if not self.api_key:
            log.error("API ключ не установлен")
            return []

        if start_date is None:
            start_date = datetime.now(timezone.utc)
        if end_date is None:
            end_date = start_date + timedelta(days=30)

        params = {
            "c": self.api_key,
            "d1": start_date.strftime("%Y-%m-%d"),
            "d2": end_date.strftime("%Y-%m-%d"),
        }
        if countries:
            params["countries"] = ",".join(countries)

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            events = []
            for item in data:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                except Exception as e:  # noqa: BLE001
                    log.debug("Ошибка при парсинге события: %s", e)
                    continue

            log.info("Загружено %s событий из TradingEconomics", len(events))
            return events
        except requests.exceptions.RequestException as e:
            log.error("Ошибка при запросе к TradingEconomics API: %s", e)
            return []

    def _parse_event(self, item: Dict) -> Optional[EconomicEvent]:
        """Парсит событие из ответа API."""
        try:
            # TradingEconomics API формат может варьироваться
            # Адаптируем под реальный формат ответа
            event_id = str(item.get("CalendarId", item.get("Id", "")))
            country = item.get("Country", "").upper()
            event_name = item.get("Event", item.get("EventName", ""))
            
            # Важность (может быть числом или строкой)
            importance_raw = item.get("Importance", "1")
            if isinstance(importance_raw, str):
                importance_map = {"High": "high", "Medium": "medium", "Low": "low"}
                importance = importance_map.get(importance_raw, "low")
            else:
                importance = "high" if importance_raw >= 2 else "medium" if importance_raw >= 1 else "low"

            # Время события
            date_str = item.get("Date", item.get("DateTime", ""))
            if isinstance(date_str, str):
                timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(timezone.utc)

            currency = item.get("Currency", "")
            actual = item.get("Actual")
            forecast = item.get("Forecast")
            previous = item.get("Previous")

            return EconomicEvent(
                event_id=event_id,
                country=country,
                event_name=event_name,
                importance=importance,
                timestamp=timestamp,
                currency=currency,
                actual=float(actual) if actual is not None else None,
                forecast=float(forecast) if forecast is not None else None,
                previous=float(previous) if previous is not None else None,
                source="tradingeconomics",
            )
        except Exception as e:  # noqa: BLE001
            log.debug("Ошибка при парсинге события: %s", e)
            return None


class ForexFactoryAdapter:
    """Адаптер для ForexFactory (через парсинг HTML)."""

    BASE_URL = "https://www.forexfactory.com/calendar"

    def fetch_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """
        Парсит события с ForexFactory.
        ВАЖНО: Это прототип, требует реализации парсинга HTML.
        """
        log.warning("ForexFactory парсинг не реализован. Используйте TradingEconomics.")
        return []


def aggregate_events(events_list: List[List[EconomicEvent]]) -> List[EconomicEvent]:
    """
    Объединяет события из разных источников и удаляет дубликаты.
    """
    seen_ids = set()
    aggregated = []

    for events in events_list:
        for event in events:
            # Используем комбинацию event_id и timestamp для дедупликации
            unique_key = (event.event_id, event.timestamp.isoformat())
            if unique_key not in seen_ids:
                seen_ids.add(unique_key)
                aggregated.append(event)

    # Сортируем по времени
    aggregated.sort(key=lambda e: e.timestamp)
    return aggregated


def save_events(events: List[EconomicEvent], output_path: Path) -> None:
    """Сохраняет события в JSONL формат."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        for event in events:
            data = {
                "event_id": event.event_id,
                "country": event.country,
                "event_name": event.event_name,
                "importance": event.importance,
                "timestamp": event.timestamp.isoformat(),
                "currency": event.currency,
                "actual": event.actual,
                "forecast": event.forecast,
                "previous": event.previous,
                "source": event.source,
            }
            fp.write(json.dumps(data, ensure_ascii=False) + "\n")
    log.info("Сохранено %s событий в %s", len(events), output_path)


def load_events(input_path: Path) -> List[EconomicEvent]:
    """Загружает события из JSONL файла."""
    if not input_path.exists():
        return []

    events = []
    with input_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                events.append(
                    EconomicEvent(
                        event_id=data["event_id"],
                        country=data["country"],
                        event_name=data["event_name"],
                        importance=data["importance"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        currency=data["currency"],
                        actual=data.get("actual"),
                        forecast=data.get("forecast"),
                        previous=data.get("previous"),
                        source=data.get("source", "unknown"),
                    )
                )
            except Exception as e:  # noqa: BLE001
                log.debug("Ошибка при загрузке события: %s", e)
                continue

    return events


def compute_news_score(
    events: List[EconomicEvent],
    timestamp: datetime,
    currency: str,
    window_minutes: int = 120,
) -> tuple[float, Optional[datetime]]:
    """
    Вычисляет news_score для заданного времени и валюты.
    
    Returns:
        (score, latest_event_time): score от -1 до 1, время последнего события
    """
    window_start = timestamp - timedelta(minutes=window_minutes)
    
    # Фильтруем события по времени и валюте
    relevant_events = [
        e
        for e in events
        if window_start <= e.timestamp <= timestamp and e.currency == currency
    ]
    
    if not relevant_events:
        return 0.0, None
    
    # Вычисляем взвешенный score на основе важности и отклонения от прогноза
    total_score = 0.0
    importance_weights = {"high": 1.0, "medium": 0.5, "low": 0.2}
    latest_event_time = max(e.timestamp for e in relevant_events)
    
    for event in relevant_events:
        weight = importance_weights.get(event.importance, 0.2)
        
        # Если есть actual и forecast, вычисляем отклонение
        if event.actual is not None and event.forecast is not None:
            deviation = (event.actual - event.forecast) / abs(event.forecast) if event.forecast != 0 else 0.0
            # Нормализуем отклонение (положительное = хорошие новости для валюты)
            score = min(1.0, max(-1.0, deviation * 10))  # Масштабируем
        else:
            # Если нет данных, используем только важность (нейтрально)
            score = 0.0
        
        total_score += score * weight
    
    # Нормализуем по количеству событий
    if relevant_events:
        total_score = total_score / len(relevant_events)
    
    return min(1.0, max(-1.0, total_score)), latest_event_time


def enrich_dataframe_with_news(
    df: pd.DataFrame,
    events: List[EconomicEvent],
    currency_map: Dict[str, str],
    window_minutes: int = 120,
) -> pd.DataFrame:
    """
    Обогащает DataFrame колонками news_score и news_time.
    
    Args:
        df: DataFrame с колонкой 'instrument' и индексом datetime
        events: Список экономических событий
        currency_map: Маппинг инструментов на валюты (например, {'EURUSD': 'EUR'})
        window_minutes: Окно для поиска событий
    """
    df = df.copy()
    df["news_score"] = 0.0
    df["news_time"] = pd.NaT
    
    for idx in df.index:
        instrument = df.loc[idx, "instrument"]
        currency = currency_map.get(instrument, "")
        if not currency:
            continue
        
        score, event_time = compute_news_score(events, idx, currency, window_minutes)
        df.loc[idx, "news_score"] = score
        if event_time:
            df.loc[idx, "news_time"] = event_time
    
    return df

