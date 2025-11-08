# Исследовательская среда форекс-стратегий

## Цель
Обеспечить воспроизводимые эксперименты, прослеживаемость результатов и стандартизированные шаблоны для разработки и тестирования алгоритмических стратегий.

## Состав среды
- **JupyterLab** — интерактивная работа с гипотезами и визуализация.
- **MLflow** — трекинг экспериментов, метрик, артефактов и параметров.
- **Prefect** — оркестрация длительных вычислений и плановых прогонов бэктестов.
- **Typer CLI** — единый интерфейс для запуска процессов из терминала.

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[backtesting]"
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
```

## Структура каталога `research/`
- `configs/experiment.yaml` — настройки по умолчанию для экспериментов.
- `templates/backtest_template.py` — опорный скрипт backtest + трекинг.
- `notebooks/` — каталог для Jupyter Notebook с соглашением `<дата>_<название>.ipynb`.
- `reports/` — автоматически сгенерированные отчёты и артефакты.
- `flows/ctrader_daily.py` — Prefect-flow для ежедневной синхронизации cTrader баров (live/demo).

## Практики воспроизводимости
- Каждая задача запускается через скрипт `research/tools/cli.py` с фиксацией версии данных и параметров.
- MLflow хранит параметры (гиперпараметры стратегии), метрики (Sharpe, max drawdown), артефакты (equity curve, отчёт в формате HTML).
- Перед публикацией результатов создаётся тег `ready_for_review`.

## Интеграции
- Оркестрация Prefect может запускать конвейер `src/data_pipeline.ingest` и ежедневный поток `ctrader_daily_backfill`.
- Параметры стратегий хранятся в `research/configs/strategy/<name>.yaml`, применяются через CLI.

