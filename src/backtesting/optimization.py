from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from itertools import product
from typing import Callable, Dict, List, Optional

import json
from pathlib import Path

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from src.backtesting.full_backtest import FullBacktestResult, FullBacktestRunner
from src.strategies import Strategy

log = logging.getLogger(__name__)


def _hash_params(params: Dict, instrument: str, period: str, optimization_metric: str) -> str:
    """Создает хэш для комбинации параметров."""
    key = json.dumps({
        "params": params,
        "instrument": instrument,
        "period": period,
        "optimization_metric": optimization_metric,
    }, sort_keys=True)
    return md5(key.encode("utf-8")).hexdigest()


def _evaluate_params(
    params: Dict,
    strategy_factory_name: str,
    runner_config: Dict,
    instrument: str,
    period: str,
    optimization_metric: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[Dict, float, Optional[str]]:
    """
    Вспомогательная функция для параллельного выполнения бэктеста.
    Выполняется в отдельном процессе.
    
    Returns:
        (params, score, error_message)
    """
    try:
        # Преобразуем строки обратно в datetime если нужно
        from datetime import datetime as dt
        start_dt = dt.fromisoformat(start_date) if start_date else None
        end_dt = dt.fromisoformat(end_date) if end_date else None
        
        # Создаем runner в каждом процессе
        # verbose_cache_load=False чтобы не засорять логи при параллельной обработке
        runner = FullBacktestRunner(
            curated_dir=Path(runner_config["curated_dir"]),
            symbol_info_path=Path(runner_config["symbol_info_path"]),
            initial_capital=runner_config["initial_capital"],
            commission_bps=runner_config["commission_bps"],
            slippage_bps=runner_config["slippage_bps"],
            verbose_cache_load=False,  # Отключаем логирование загрузки кэша в параллельных процессах
        )
        
        # Импортируем стратегии
        from src.strategies import (
            BollingerReversionStrategy,
            CarryMomentumStrategy,
            CombinedMomentumStrategy,
            MACDTrendStrategy,
            MeanReversionStrategy,
            MomentumBreakoutStrategy,
        )
        
        # Создаем стратегию на основе имени
        strategy_map = {
            "momentum_breakout": MomentumBreakoutStrategy,
            "carry_momentum": CarryMomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "combined_momentum": CombinedMomentumStrategy,
            "macd_trend": MACDTrendStrategy,
            "bollinger_reversion": BollingerReversionStrategy,
        }
        
        strategy_class = strategy_map.get(strategy_factory_name)
        if strategy_class is None:
            raise ValueError(f"Неизвестная стратегия: {strategy_factory_name}")
        
        strategy = strategy_class(**params)
        result = runner.run(strategy, instrument, period, start_dt, end_dt)
        
        # Проверяем валидность результата перед использованием Recovery Factor
        # Recovery Factor = inf когда max_drawdown = 0, что может быть из-за отсутствия сделок
        # или отсутствия просадок. Нужно учитывать количество сделок.
        if optimization_metric == "recovery_factor":
            # Если нет сделок или очень мало сделок, Recovery Factor должен быть низким
            if result.total_trades == 0:
                score = 0.0
            elif result.total_trades < 5:  # Минимум 5 сделок для валидной оценки
                score = result.recovery_factor if result.recovery_factor != float("inf") else 0.0
            elif result.recovery_factor == float("inf"):
                # Если Recovery Factor = inf (нет просадок), но есть сделки - это хорошо, но ограничим
                # Используем комбинацию метрик: если нет просадок и есть прибыль, это отличный результат
                # Но ограничим до разумного значения (например, 100) чтобы не доминировал над другими метриками
                if result.net_pnl > 0:
                    score = 100.0  # Ограничиваем inf до 100 для сравнения
                else:
                    score = 0.0
            else:
                score = result.recovery_factor
        elif optimization_metric == "sharpe_ratio":
            score = result.sharpe_ratio
        elif optimization_metric == "net_pnl":
            score = result.net_pnl
        elif optimization_metric == "profit_factor":
            score = result.profit_factor if result.profit_factor > 0 else 0.0
        else:
            raise ValueError(f"Неизвестная метрика: {optimization_metric}")
        
        return (params, score, None)
    except Exception as e:
        return (params, float("-inf"), str(e))


@dataclass(slots=True)
class OptimizationResult:
    """Результат оптимизации параметров."""

    best_params: Dict
    best_score: float
    all_results: List[tuple[Dict, float]]
    optimization_metric: str


class HyperparameterOptimizer:
    """Оптимизация гиперпараметров стратегий через grid search."""

    def __init__(self, runner: FullBacktestRunner, cache_dir: Optional[Path] = None):
        self.runner = runner
        self.cache_dir = cache_dir or Path("data/v1/cache/optimization")
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def optimize(
        self,
        strategy_factory: Callable[[Dict], Strategy],
        param_grid: Dict[str, List],
        instrument: str,
        period: str = "m15",
        optimization_metric: str = "sharpe_ratio",  # sharpe_ratio, recovery_factor, net_pnl, profit_factor
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        n_jobs: int = 1,
        early_stopping_threshold: Optional[float] = None,
        stage_info: Optional[str] = None,  # Информация об этапе для логирования (например, "Этап 1/2")
    ) -> OptimizationResult:
        """
        Выполняет grid search оптимизацию параметров.
        
        Args:
            strategy_factory: Функция, принимающая словарь параметров и возвращающая Strategy
            param_grid: Словарь с параметрами и их возможными значениями
            instrument: Инструмент для тестирования
            period: Период данных
            optimization_metric: Метрика для оптимизации (sharpe_ratio, recovery_factor, net_pnl, profit_factor)
            start_date: Начальная дата
            end_date: Конечная дата
            n_jobs: Количество параллельных процессов (1 = последовательное выполнение)
            early_stopping_threshold: Порог для раннего прекращения (если результат < threshold * best_score, пропускаем)
        """
        # Генерируем все комбинации параметров
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))

        log.info("Начинаем оптимизацию: %s комбинаций параметров (n_jobs=%s)", len(param_combinations), n_jobs)

        # Определяем имя стратегии из factory функции (создаем стратегию с дефолтными параметрами)
        try:
            # Пробуем создать стратегию с пустыми параметрами для получения strategy_id
            test_strategy = strategy_factory({})
            strategy_name = test_strategy.strategy_id
        except Exception:
            # Если не получилось, пробуем создать с первыми значениями из grid
            try:
                test_params = {name: values[0] for name, values in param_grid.items()}
                test_strategy = strategy_factory(test_params)
                strategy_name = test_strategy.strategy_id
            except Exception:
                log.warning("Не удалось определить имя стратегии, используем 'unknown'")
                strategy_name = "unknown"
        
        # Подготавливаем конфигурацию runner для передачи в процессы
        runner_config = {
            "curated_dir": str(self.runner.curated_dir),
            "symbol_info_path": str(self.runner.symbol_cache._cache_path),
            "initial_capital": self.runner.initial_capital,
            "commission_bps": self.runner.commission_bps,
            "slippage_bps": self.runner.slippage_bps,
        }

        all_results: List[tuple[Dict, float]] = []
        best_score = float("-inf")
        best_params = None
        cache_hits = 0

        if n_jobs == 1:
            # Последовательное выполнение (оригинальный код)
            iterator = enumerate(param_combinations)
            if HAS_TQDM:
                iterator = tqdm(iterator, total=len(param_combinations), desc="Оптимизация")
            
            for i, param_combo in iterator:
                params = dict(zip(param_names, param_combo))
                
                # Проверяем кэш
                cache_key = _hash_params(params, instrument, period, optimization_metric)
                cache_path = self.cache_dir / f"{cache_key}.json" if self.cache_dir else None
                
                score = None
                if cache_path and cache_path.exists():
                    try:
                        with cache_path.open("r", encoding="utf-8") as fp:
                            cached_data = json.load(fp)
                            score = cached_data.get("score")
                            if score is not None:
                                cache_hits += 1
                                log.debug("Кэш попадание для параметров: %s (score=%.4f)", params, score)
                    except Exception:
                        pass
                
                if score is None:
                    try:
                        strategy = strategy_factory(params)
                        result = self.runner.run(strategy, instrument, period, start_date, end_date)

                        # Извлекаем метрику
                        if optimization_metric == "sharpe_ratio":
                            score = result.sharpe_ratio
                        elif optimization_metric == "recovery_factor":
                            # Проверяем валидность результата
                            if result.total_trades == 0:
                                score = 0.0
                            elif result.total_trades < 5:
                                score = result.recovery_factor if result.recovery_factor != float("inf") else 0.0
                            elif result.recovery_factor == float("inf"):
                                # Ограничиваем inf до 100 для сравнения
                                score = 100.0 if result.net_pnl > 0 else 0.0
                            else:
                                score = result.recovery_factor
                        elif optimization_metric == "net_pnl":
                            score = result.net_pnl
                        elif optimization_metric == "profit_factor":
                            score = result.profit_factor if result.profit_factor > 0 else 0.0
                        else:
                            raise ValueError(f"Неизвестная метрика: {optimization_metric}")

                        # Сохраняем в кэш
                        if cache_path:
                            try:
                                with cache_path.open("w", encoding="utf-8") as fp:
                                    json.dump({"params": params, "score": float(score)}, fp, ensure_ascii=False, indent=2)
                            except Exception:
                                pass

                    except Exception as e:  # noqa: BLE001
                        log.error("Ошибка при тестировании параметров %s: %s", params, e)
                        continue

                # Применяем раннее прекращение перед добавлением в результаты
                if early_stopping_threshold and best_score != float("-inf") and score < early_stopping_threshold * best_score:
                    log.debug("Пропущен результат ниже порога: %.4f < %.4f * %.4f", 
                             score, early_stopping_threshold, best_score)
                    continue

                all_results.append((params, score))

                if score > best_score:
                    best_score = score
                    best_params = params
                    log.info("Новый лучший результат: %s = %.4f", optimization_metric, score)
        else:
            # Параллельное выполнение
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                # Отправляем все задачи
                futures = {}
                for param_combo in param_combinations:
                    params = dict(zip(param_names, param_combo))
                    
                    # Проверяем кэш перед отправкой задачи
                    cache_key = _hash_params(params, instrument, period, optimization_metric)
                    cache_path = self.cache_dir / f"{cache_key}.json" if self.cache_dir else None
                    
                    cached_score = None
                    if cache_path and cache_path.exists():
                        try:
                            with cache_path.open("r", encoding="utf-8") as fp:
                                cached_data = json.load(fp)
                                cached_score = cached_data.get("score")
                                if cached_score is not None:
                                    cache_hits += 1
                                    log.debug("Кэш попадание для параметров: %s (score=%.4f)", params, cached_score)
                                    # Добавляем кэшированный результат сразу
                                    all_results.append((params, cached_score))
                                    if cached_score > best_score:
                                        best_score = cached_score
                                        best_params = params
                                    continue
                        except Exception:
                            pass
                    
                    # Преобразуем datetime в строки для сериализации
                    start_date_str = start_date.isoformat() if start_date else None
                    end_date_str = end_date.isoformat() if end_date else None
                    future = executor.submit(
                        _evaluate_params,
                        params,
                        strategy_name,
                        runner_config,
                        instrument,
                        period,
                        optimization_metric,
                        start_date_str,
                        end_date_str,
                    )
                    futures[future] = (params, cache_path)

                # Собираем результаты с прогресс-баром
                iterator = as_completed(futures)
                if HAS_TQDM:
                    iterator = tqdm(iterator, total=len(futures), desc="Оптимизация")
                
                for future in iterator:
                    params, cache_path = futures[future]
                    try:
                        # Добавляем timeout чтобы процессы не зависали бесконечно
                        result_params, score, error = future.result(timeout=300)  # 5 минут на одну комбинацию
                    except TimeoutError:
                        log.error("Таймаут при тестировании параметров %s (превышено 5 минут)", params)
                        # Отменяем задачу и продолжаем
                        future.cancel()
                        continue
                    except Exception as e:
                        log.error("Ошибка при получении результата для параметров %s: %s", params, e)
                        continue
                    
                    # Сохраняем в кэш
                    if cache_path:
                        try:
                            with cache_path.open("w", encoding="utf-8") as fp:
                                json.dump({"params": params, "score": float(score)}, fp, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                    
                    # Применяем раннее прекращение
                    if early_stopping_threshold and best_score != float("-inf") and score < early_stopping_threshold * best_score:
                        log.debug("Пропущен результат ниже порога: %.4f < %.4f * %.4f", 
                                 score, early_stopping_threshold, best_score)
                        continue
                    
                    all_results.append((params, score))
                    
                    if score > best_score:
                        best_score = score
                        best_params = params
                        log.info("Новый лучший результат: %s = %.4f", optimization_metric, score)
                    
                    # Промежуточное сохранение каждые 50 комбинаций (только для параллельного режима)
                    if len(all_results) % 50 == 0:
                        stage_prefix = f"{stage_info} - " if stage_info else ""
                        log.info("%sПромежуточный прогресс: протестировано %s из %s комбинаций (%.1f%%)", 
                                stage_prefix, len(all_results), len(futures), 
                                len(all_results) / len(futures) * 100 if len(futures) > 0 else 0)

        if cache_hits > 0:
            log.info("Кэш попаданий: %s из %s комбинаций", cache_hits, len(param_combinations))

        log.info("Оптимизация завершена. Лучшие параметры: %s (score=%.4f)", best_params, best_score)

        return OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            all_results=all_results,
            optimization_metric=optimization_metric,
        )

    def save_best_params(self, result: OptimizationResult, output_path: Path) -> None:
        """Сохраняет лучшие параметры в JSON файл."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "optimization_metric": result.optimization_metric,
            "best_score": result.best_score,
            "best_params": result.best_params,
            "optimized_at": datetime.now().isoformat(),
        }
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        log.info("Лучшие параметры сохранены в %s", output_path)

    def save_all_results(self, result: OptimizationResult, output_path: Path) -> None:
        """Сохраняет все результаты оптимизации в JSON файл для анализа."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "optimization_metric": result.optimization_metric,
            "best_score": result.best_score,
            "best_params": result.best_params,
            "total_combinations": len(result.all_results),
            "optimized_at": datetime.now().isoformat(),
            "all_results": [
                {"params": params, "score": float(score)} 
                for params, score in result.all_results
            ],
        }
        with output_path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        log.info("Все результаты оптимизации сохранены в %s (%s комбинаций)", output_path, len(result.all_results))

