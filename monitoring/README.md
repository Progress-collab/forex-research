# Мониторинг и алертинг

## Архитектура
- **Prometheus** собирает метрики из сервисов исполнения, стратегий и риск-движка.
- **Grafana** визуализирует панели из `monitoring/dashboard_config.yaml`.
- **Alertmanager** генерирует уведомления по правилам `monitoring/alerts.yaml`.
- **Log Aggregation** (ELK/OpenSearch) для журналов стратегий и брокера.

## Потоки данных
1. Сервисы публикуют метрики через Prometheus client.
2. Экспортёры записывают метрики latency, fill rate, PnL, risk limits.
3. Alertmanager доставляет уведомления в Slack/Telegram.
4. Runbooks описывают реакцию на инциденты.
5. Скрипт `python -m research.backtests.run_baseline` формирует отчёт и агрегированные показатели бэктестов; результаты выгружаются в `research/reports/*.md` и могут пушиться в Prometheus (метрики `strategy_sharpe`, `strategy_recovery_factor`, `strategy_win_rate`).

## Регулярные проверки
- Раз в день: сверка доступности дашбордов, корректности метрик.
- Раз в неделю: проверка точности алертов (test firing), обновление recovery factor.
- Раз в месяц: обновление порогов и review новых стратегий.

## Итерационный цикл
- Использовать результаты Prefect-бэктестов для обновления метрик `strategy_sharpe`, `strategy_recovery_factor`.
- После каждого изменения параметров стратегии фиксировать baseline в MLflow и сравнивать с live-метриками.
- План мониторинга:
  - **Prefect flow** запускает `research/backtests/run_baseline.py` ежедневно и публикует значения win-rate и PnL через кастомный экспортёр.
  - **Prometheus job `fxpro_strategies`** собирает метрики `strategy_health` и `strategy_recovery_factor` для графиков (`monitoring/dashboard_config.yaml`).
  - **Alert `StrategyRecoveryDrop`** триггерит при снижении recovery factor < 1.0 (см. `monitoring/alerts.yaml`).

