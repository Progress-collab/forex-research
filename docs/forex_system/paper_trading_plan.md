# План запуска роботов в бумажном контуре FXPro (cTrader)

## 1. Подготовка окружения
- Получить демо-учётные данные FXPro cTrader (Raw+), активировать API-доступ.
- Создать JSON-файл `secrets/ctrader_demo.json` (см. пример `secrets/ctrader_demo.example.json`) с полями `client_id`, `client_secret`, `access_token`, `account_id`, `base_url`.
- В `.env` прописать `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_ACCESS_TOKEN`, `CTRADER_REFRESH_TOKEN`.
- Настроить Python-окружение: `pip install -e ".[backtesting]"`, запустить Prefect и MLflow сервисы.

## 2. Сбор данных и расчёт признаков
- Запустить `scripts/run_ingest.py --secid EURUSD_TOD` (или соответствующие тикеры FXPro) для загрузки исторических свечей.
- Убедиться, что данные сохранены в `data/v1/raw/candles/`.
- Выполнить `python -m research.tools.cli backtest --variant default` для Smoke-теста стратегии.
- Для FXPro использовать `python -m scripts.fetch_ctrader_trendbars --symbol EURUSD --period m15 --bars 1000 --output data/v1/raw/eurusd_m15.jsonl` (по умолчанию live).

## 3. Регистрация стратегий в исполнении
- Заготовить файл `config/strategies.json`:
  ```json
  [
    {"strategy_id": "momentum_breakout", "max_notional": 200000, "max_leverage": 2.0, "max_orders_per_minute": 20},
    {"strategy_id": "mean_reversion", "max_notional": 150000, "max_leverage": 1.8, "max_orders_per_minute": 25},
    {"strategy_id": "carry_momentum", "max_notional": 120000, "max_leverage": 2.5, "max_orders_per_minute": 10},
    {"strategy_id": "intraday_liquidity_breakout", "max_notional": 150000, "max_leverage": 2.0, "max_orders_per_minute": 15},
    {"strategy_id": "volatility_compression", "max_notional": 120000, "max_leverage": 1.8, "max_orders_per_minute": 15}
  ]
  ```
- Массово зарегистрировать стратегии:
  ```bash
  python -m src.execution.cli register-batch config/strategies.json
  ```
- Импортировать стратегии:
  ```bash
  python -m src.execution.cli use-ctrader --config secrets/ctrader_demo.json
  ```
  (для локальных тестов можно оставить режим dummy-диспетчера и пропустить шаг `use-ctrader`).
- Выполнить dry-run без подключения к брокеру:
  ```bash
  python -m scripts.paper_dry_run --config config/strategies.json --simulate-orders --instrument EURUSD
  ```
  Скрипт добавит стратегии в локальное состояние (`state/paper_dry_run.json`) и отправит тестовые market-ордера через mock-диспетчер. Это позволяет проверить конфигурации перед реальной интеграцией.

## 4. Настройка Prefect Flow
- Зарегистрировать `daily_backtest_flow` с интервалом 1 час (см. `research/flows/daily_backtests.py`).
- Создать дополнительный flow для генерации сигналов и отправки в execution (после smoke-теста).

## 5. Мониторинг бумажного контура
- Включить Prometheus/Grafana, настроить алерты из `monitoring/alerts.yaml`.
- Проверять latency, fill rate, расхождения PnL vs backtest.

## 6. Критерии перехода в прод
- Минимум 4 недели бумажного теста без превышения просадки 5% по каждой стратегии.
- Sharpe (paper) ≥ 1.0 и Recovery Factor ≥ 1.5 на интервале теста.
- Не более 1 критического инцидента (по runbooks) за период.
- Подтверждение Risk Manager и Investment Committee.

