"""Генетический алгоритм оптимизации параметров стратегий."""
from __future__ import annotations

import logging
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

import json
from pathlib import Path

try:
    import numpy as np
    from deap import base, creator, tools
    HAS_DEAP = True
except ImportError:
    HAS_DEAP = False

from src.backtesting.full_backtest import FullBacktestRunner
from src.backtesting.optimization import OptimizationResult, _evaluate_params, _hash_params
from src.strategies import Strategy

log = logging.getLogger(__name__)


def _evaluate_individual_parallel(
    individual_data: tuple,
    strategy_factory_name: str,
    runner_config: Dict,
    instrument: str,
    period: str,
    optimization_metric: str,
    start_date: Optional[str],
    end_date: Optional[str],
    cache_dir: str,
) -> tuple[List, float]:
    """
    Вспомогательная функция для параллельной оценки индивида.
    Выполняется в отдельном процессе.
    
    Args:
        individual_data: Кортеж (individual_list, params_dict) для сериализации
        strategy_factory_name: Имя стратегии для создания
        runner_config: Конфигурация runner как словарь
        instrument: Инструмент
        period: Период
        optimization_metric: Метрика оптимизации
        start_date: Начальная дата (строка)
        end_date: Конечная дата (строка)
        cache_dir: Путь к директории кэша (строка)
    
    Returns:
        (individual_list, score)
    """
    individual_list, params = individual_data
    
    # Проверяем кэш
    cache_path = Path(cache_dir) / f"{_hash_params(params, instrument, period, optimization_metric)}.json"
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as fp:
                cached_data = json.load(fp)
                score = cached_data.get("score")
                if score is not None:
                    return (individual_list, score)
        except Exception:
            pass
    
    # Используем существующую функцию _evaluate_params
    params_dict, score, error = _evaluate_params(
        params=params,
        strategy_factory_name=strategy_factory_name,
        runner_config=runner_config,
        instrument=instrument,
        period=period,
        optimization_metric=optimization_metric,
        start_date=start_date,
        end_date=end_date,
    )
    
    if error:
        return (individual_list, float("-inf"))
    
    return (individual_list, score)


def _evaluate_wrapper_for_deap(
    individual: List,
    strategy_factory_name: str,
    runner_config: Dict,
    instrument: str,
    period: str,
    optimization_metric: str,
    start_date_str: Optional[str],
    end_date_str: Optional[str],
    cache_dir_str: str,
) -> tuple[float]:
    """
    Обертка для параллельной оценки индивида в DEAP.
    Выполняется в отдельном процессе.
    """
    # Преобразуем individual в params
    params = {param_name: value for param_name, value in individual}
    individual_data = (list(individual), params)
    
    individual_list, score = _evaluate_individual_parallel(
        individual_data=individual_data,
        strategy_factory_name=strategy_factory_name,
        runner_config=runner_config,
        instrument=instrument,
        period=period,
        optimization_metric=optimization_metric,
        start_date=start_date_str,
        end_date=end_date_str,
        cache_dir=cache_dir_str,
    )
    return (score,)


class GeneticOptimizer:
    """Генетический алгоритм для оптимизации гиперпараметров стратегий."""

    def __init__(
        self,
        runner: FullBacktestRunner,
        cache_dir: Optional[Path] = None,
        n_generations: int = 20,
        population_size: int = 50,
        mutation_prob: float = 0.2,
        crossover_prob: float = 0.7,
        tournament_size: int = 3,
        elite_size: int = 5,
        early_stopping_patience: Optional[int] = None,  # Количество поколений без улучшения для раннего прекращения
        use_fast_evaluation: bool = False,  # Использовать быструю оценку с подвыборкой данных
        fast_evaluation_months: int = 6,  # Количество месяцев для быстрой оценки
    ):
        """
        Инициализация генетического оптимизатора.
        
        Args:
            runner: Бэктест раннер
            cache_dir: Директория для кэша результатов
            n_generations: Количество поколений
            population_size: Размер популяции
            mutation_prob: Вероятность мутации
            crossover_prob: Вероятность скрещивания
            tournament_size: Размер турнира для селекции
            elite_size: Количество лучших особей для элитизма
        """
        if not HAS_DEAP:
            raise ImportError("DEAP не установлен. Установите: pip install deap")
        
        self.runner = runner
        self.cache_dir = cache_dir or Path("data/v1/cache/optimization")
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.n_generations = n_generations
        self.population_size = population_size
        self.mutation_prob = mutation_prob
        self.crossover_prob = crossover_prob
        self.tournament_size = tournament_size
        self.elite_size = elite_size
        self.early_stopping_patience = early_stopping_patience
        self.use_fast_evaluation = use_fast_evaluation
        self.fast_evaluation_months = fast_evaluation_months
        
        # In-memory кэш для результатов текущей сессии
        self._memory_cache: Dict[str, float] = {}
        
        # Инициализация DEAP
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMax)
        
        self.toolbox = base.Toolbox()
        self.toolbox.register("select", tools.selTournament, tournsize=tournament_size)

    def _create_individual(self, param_grid: Dict[str, List]) -> List:
        """Создает случайного индивида из param_grid."""
        individual = []
        for param_name, param_values in param_grid.items():
            if isinstance(param_values[0], (int, float)):
                # Непрерывный параметр - выбираем случайное значение из диапазона
                if isinstance(param_values[0], int):
                    value = random.choice(param_values)
                else:
                    value = random.uniform(min(param_values), max(param_values))
                individual.append((param_name, value))
            else:
                # Дискретный параметр - выбираем случайное значение
                value = random.choice(param_values)
                individual.append((param_name, value))
        return individual

    def _mutate(self, individual: List, param_grid: Dict[str, List], indpb: float = 0.3) -> tuple:
        """Мутирует индивида."""
        for i, (param_name, value) in enumerate(individual):
            if random.random() < indpb:
                param_values = param_grid[param_name]
                if isinstance(param_values[0], (int, float)):
                    if isinstance(param_values[0], int):
                        # Для целых чисел выбираем новое значение из списка
                        individual[i] = (param_name, random.choice(param_values))
                    else:
                        # Для вещественных чисел добавляем небольшое случайное изменение
                        min_val = min(param_values)
                        max_val = max(param_values)
                        range_val = max_val - min_val
                        mutation = random.gauss(0, range_val * 0.1)  # 10% от диапазона
                        new_value = max(min_val, min(max_val, value + mutation))
                        individual[i] = (param_name, new_value)
                else:
                    # Для других типов выбираем случайное значение
                    individual[i] = (param_name, random.choice(param_values))
        return individual,

    def _crossover(self, ind1: List, ind2: List) -> tuple:
        """Скрещивает двух индивидов."""
        # Простое одноточечное скрещивание
        if len(ind1) > 1:
            point = random.randint(1, len(ind1) - 1)
            ind1[point:], ind2[point:] = ind2[point:], ind1[point:]
        return ind1, ind2

    def _individual_to_params(self, individual: List) -> Dict:
        """Преобразует индивида в словарь параметров."""
        return {param_name: value for param_name, value in individual}

    def _evaluate(
        self,
        individual: List,
        strategy_factory: Callable[[Dict], Strategy],
        instrument: str,
        period: str,
        optimization_metric: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> tuple[float]:
        """Оценивает фитнес индивида."""
        params = self._individual_to_params(individual)
        
        # Проверяем in-memory кэш сначала (быстрее чем файловый)
        cache_key = _hash_params(params, instrument, period, optimization_metric)
        if cache_key in self._memory_cache:
            return (self._memory_cache[cache_key],)
        
        # Проверяем файловый кэш
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            try:
                with cache_path.open("r", encoding="utf-8") as fp:
                    cached_data = json.load(fp)
                    score = cached_data.get("score")
                    if score is not None:
                        # Сохраняем в in-memory кэш для будущих обращений
                        self._memory_cache[cache_key] = score
                        return (score,)
            except Exception:
                pass
        
        # Запускаем бэктест
        try:
            strategy = strategy_factory(params)
            result = self.runner.run(strategy, instrument, period, start_date, end_date)
            
            # Извлекаем метрику
            if optimization_metric == "recovery_factor":
                if result.total_trades == 0:
                    score = 0.0
                elif result.total_trades < 5:
                    score = result.recovery_factor if result.recovery_factor != float("inf") else 0.0
                elif result.recovery_factor == float("inf"):
                    score = 100.0 if result.net_pnl > 0 else 0.0
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
            
            # Сохраняем в оба кэша
            self._memory_cache[cache_key] = score
            if cache_path:
                try:
                    with cache_path.open("w", encoding="utf-8") as fp:
                        json.dump({"params": params, "score": float(score)}, fp, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            
            return (score,)
        except Exception as e:
            log.error("Ошибка при оценке индивида %s: %s", params, e)
            return (float("-inf"),)

    def optimize(
        self,
        strategy_factory: Callable[[Dict], Strategy],
        param_grid: Dict[str, List],
        instrument: str,
        period: str = "m15",
        optimization_metric: str = "recovery_factor",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        n_jobs: int = 1,
        strategy_factory_name: Optional[str] = None,
        intermediate_save_path: Optional[Path] = None,
    ) -> OptimizationResult:
        """
        Выполняет генетическую оптимизацию параметров.
        
        Args:
            strategy_factory: Функция, создающая стратегию из параметров
            param_grid: Словарь с параметрами и их возможными значениями
            instrument: Инструмент для тестирования
            period: Период данных
            optimization_metric: Метрика для оптимизации
            start_date: Начальная дата
            end_date: Конечная дата
            n_jobs: Количество параллельных процессов (12 по умолчанию для ускорения)
            strategy_factory_name: Имя стратегии для сериализации (если None, будет определено автоматически)
        
        Returns:
            OptimizationResult с лучшими параметрами и всеми результатами
        """
        # Очищаем in-memory кэш перед началом оптимизации
        self._memory_cache.clear()
        
        # Определяем имя стратегии если не указано
        if strategy_factory_name is None:
            # Пробуем определить по типу стратегии из factory
            test_params = {k: v[0] if v else None for k, v in param_grid.items()}
            test_strategy = strategy_factory(test_params)
            strategy_factory_name = test_strategy.strategy_id
        
        # Вычисляем даты для быстрой оценки если нужно
        fast_start_date = None
        fast_end_date = end_date
        if self.use_fast_evaluation and end_date:
            from datetime import timedelta
            fast_start_date = end_date - timedelta(days=self.fast_evaluation_months * 30)
        
        # Подготавливаем конфигурацию runner для сериализации
        runner_config = {
            "curated_dir": str(self.runner.curated_dir),
            "symbol_info_path": str(self.runner.symbol_cache._cache_path) if hasattr(self.runner.symbol_cache, "_cache_path") else None,
            "initial_capital": self.runner.initial_capital,
            "commission_bps": self.runner.commission_bps,
            "slippage_bps": self.runner.slippage_bps,
        }
        
        # Преобразуем datetime в строки для сериализации
        start_date_str = start_date.isoformat() if start_date else None
        end_date_str = end_date.isoformat() if end_date else None
        fast_start_date_str = fast_start_date.isoformat() if fast_start_date else None
        cache_dir_str = str(self.cache_dir)
        
        # Регистрируем функции для DEAP
        def make_individual():
            ind_list = self._create_individual(param_grid)
            ind = creator.Individual(ind_list)
            ind.fitness = creator.FitnessMax()
            return ind
        
        self.toolbox.register("individual", make_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("mate", self._crossover)
        self.toolbox.register("mutate", self._mutate, param_grid=param_grid)
        
        # Настраиваем параллелизацию
        if n_jobs > 1:
            # Параллельная оценка через ProcessPoolExecutor
            log.info("Используется параллелизация: %s процессов", n_jobs)
            
            # Используем функцию на уровне модуля для сериализации
            self.toolbox.register(
                "evaluate",
                _evaluate_wrapper_for_deap,
                strategy_factory_name=strategy_factory_name,
                runner_config=runner_config,
                instrument=instrument,
                period=period,
                optimization_metric=optimization_metric,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
                cache_dir_str=cache_dir_str,
            )
            
            # Используем ProcessPoolExecutor для параллельной оценки
            executor = None
            try:
                executor = ProcessPoolExecutor(max_workers=n_jobs)
                self.toolbox.register("map", executor.map)
                
                # Создаем начальную популяцию
                population = self.toolbox.population(n=self.population_size)
                
                # Оцениваем начальную популяцию
                log.info("Оценка начальной популяции (%s особей)...", self.population_size)
                fitnesses = list(self.toolbox.map(self.toolbox.evaluate, population))
                for ind, fit in zip(population, fitnesses):
                    ind.fitness.values = fit
                
                # Сохраняем все результаты
                all_results = []
                best_score = float("-inf")
                best_params = {}
                no_improvement_count = 0  # Счетчик поколений без улучшения для early stopping
                
                for gen in range(self.n_generations):
                    # Адаптивные параметры: уменьшаем мутацию со временем
                    # Начинаем с высокой мутацией (0.3-0.4), заканчиваем низкой (0.1)
                    current_mutation_prob = self.mutation_prob * (1.0 - gen / self.n_generations * 0.5) + 0.1
                    # Адаптируем crossover_prob: увеличиваем в начале, уменьшаем в конце
                    current_crossover_prob = self.crossover_prob * (1.0 + gen / self.n_generations * 0.2)
                    current_crossover_prob = min(0.9, current_crossover_prob)  # Ограничиваем максимумом
                    
                    # Определяем использовать ли быструю оценку (только для начальных поколений)
                    use_fast = self.use_fast_evaluation and gen < self.n_generations // 2
                    eval_start_date_str = fast_start_date_str if use_fast else start_date_str
                    
                    # Сортируем популяцию по фитнесу
                    population.sort(key=lambda x: x.fitness.values[0], reverse=True)
                    
                    # Обновляем лучший результат
                    current_best = population[0]
                    current_best_score = current_best.fitness.values[0]
                    if current_best_score > best_score:
                        best_score = current_best_score
                        best_params = self._individual_to_params(current_best)
                        no_improvement_count = 0  # Сбрасываем счетчик при улучшении
                        log.info("Поколение %s/%s: новый лучший результат %s = %.4f (мутация=%.3f, crossover=%.3f)", 
                                gen + 1, self.n_generations, optimization_metric, best_score,
                                current_mutation_prob, current_crossover_prob)
                    else:
                        no_improvement_count += 1
                        if gen % 5 == 0:  # Логируем каждые 5 поколений
                            log.info("Поколение %s/%s: лучший результат %s = %.4f (без улучшения %s поколений)", 
                                    gen + 1, self.n_generations, optimization_metric, best_score, no_improvement_count)
                    
                    # Раннее прекращение если нет улучшения N поколений подряд
                    if self.early_stopping_patience and no_improvement_count >= self.early_stopping_patience:
                        log.info("Раннее прекращение: лучший результат не улучшался %s поколений подряд. Завершаем оптимизацию.", 
                                self.early_stopping_patience)
                        break
                    
                    # Сохраняем результаты текущего поколения
                    for ind in population:
                        params = self._individual_to_params(ind)
                        score = ind.fitness.values[0]
                        all_results.append((params, score))
                    
                    # Промежуточное сохранение результатов после каждого поколения
                    if intermediate_save_path:
                        try:
                            from src.backtesting.optimization import HyperparameterOptimizer
                            temp_result = OptimizationResult(
                                best_params=best_params or {},
                                best_score=best_score if best_score != float("-inf") else 0.0,
                                all_results=all_results.copy(),
                                optimization_metric=optimization_metric,
                            )
                            optimizer_temp = HyperparameterOptimizer(self.runner)
                            optimizer_temp.save_all_results(temp_result, intermediate_save_path)
                            log.debug("Промежуточные результаты сохранены: поколение %s/%s, комбинаций: %s", 
                                    gen + 1, self.n_generations, len(all_results))
                        except Exception as e:
                            log.warning("Ошибка при промежуточном сохранении: %s", e)
                    
                    # Элитизм: сохраняем лучших особей
                    elite = population[:self.elite_size]
                    
                    # Селекция и скрещивание
                    offspring = []
                    for _ in range(self.population_size - self.elite_size):
                        # Выбираем двух родителей
                        parent1 = self.toolbox.select(population, 1)[0]
                        parent2 = self.toolbox.select(population, 1)[0]
                        
                        # Скрещивание
                        child1 = creator.Individual(list(parent1))
                        child2 = creator.Individual(list(parent2))
                        child1.fitness = creator.FitnessMax()
                        child2.fitness = creator.FitnessMax()
                        # Скрещивание с адаптивной вероятностью
                        if random.random() < current_crossover_prob:
                            child1, child2 = self.toolbox.mate(child1, child2)
                            del child1.fitness.values
                            del child2.fitness.values
                        
                        offspring.append(child1)
                        if len(offspring) < self.population_size - self.elite_size:
                            offspring.append(child2)
                    
                    # Мутация с адаптивной вероятностью
                    for mutant in offspring:
                        if random.random() < current_mutation_prob:
                            self.toolbox.mutate(mutant)
                            del mutant.fitness.values
                    
                    # Оценка новых особей (параллельно)
                    invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                    if invalid_ind:
                        # Обновляем функцию evaluate для использования правильных дат
                        if use_fast:
                            # Перерегистрируем evaluate с быстрыми датами для этого поколения
                            self.toolbox.register(
                                "evaluate",
                                _evaluate_wrapper_for_deap,
                                strategy_factory_name=strategy_factory_name,
                                runner_config=runner_config,
                                instrument=instrument,
                                period=period,
                                optimization_metric=optimization_metric,
                                start_date_str=eval_start_date_str,
                                end_date_str=end_date_str,
                                cache_dir_str=cache_dir_str,
                            )
                        fitnesses = list(self.toolbox.map(self.toolbox.evaluate, invalid_ind))
                        for ind, fit in zip(invalid_ind, fitnesses):
                            ind.fitness.values = fit
                    
                    # Формируем новое поколение
                    population = elite + offspring[:self.population_size - self.elite_size]
            finally:
                # Явно закрываем executor и все процессы
                if executor is not None:
                    log.debug("Закрытие ProcessPoolExecutor и завершение всех рабочих процессов...")
                    executor.shutdown(wait=True, cancel_futures=False)
                    log.debug("ProcessPoolExecutor закрыт")
        else:
            # Последовательная оценка (старый код)
            self.toolbox.register(
                "evaluate",
                self._evaluate,
                strategy_factory=strategy_factory,
                instrument=instrument,
                period=period,
                optimization_metric=optimization_metric,
                start_date=start_date,
                end_date=end_date,
            )
            self.toolbox.register("map", map)
            
            # Создаем начальную популяцию
            population = self.toolbox.population(n=self.population_size)
            
            # Оцениваем начальную популяцию
            log.info("Оценка начальной популяции (%s особей)...", self.population_size)
            fitnesses = list(self.toolbox.map(self.toolbox.evaluate, population))
            for ind, fit in zip(population, fitnesses):
                ind.fitness.values = fit
            
            # Сохраняем все результаты
            all_results = []
            best_score = float("-inf")
            best_params = {}
            
            for gen in range(self.n_generations):
                # Сортируем популяцию по фитнесу
                population.sort(key=lambda x: x.fitness.values[0], reverse=True)
                
                # Обновляем лучший результат
                current_best = population[0]
                current_best_score = current_best.fitness.values[0]
                if current_best_score > best_score:
                    best_score = current_best_score
                    best_params = self._individual_to_params(current_best)
                    log.info("Поколение %s/%s: новый лучший результат %s = %.4f", 
                            gen + 1, self.n_generations, optimization_metric, best_score)
                
                # Сохраняем результаты текущего поколения
                for ind in population:
                    params = self._individual_to_params(ind)
                    score = ind.fitness.values[0]
                    all_results.append((params, score))
                
                # Элитизм: сохраняем лучших особей
                elite = population[:self.elite_size]
                
                # Селекция и скрещивание
                offspring = []
                for _ in range(self.population_size - self.elite_size):
                    # Выбираем двух родителей
                    parent1 = self.toolbox.select(population, 1)[0]
                    parent2 = self.toolbox.select(population, 1)[0]
                    
                    # Скрещивание
                    child1 = creator.Individual(list(parent1))
                    child2 = creator.Individual(list(parent2))
                    child1.fitness = creator.FitnessMax()
                    child2.fitness = creator.FitnessMax()
                    if random.random() < self.crossover_prob:
                        child1, child2 = self.toolbox.mate(child1, child2)
                        del child1.fitness.values
                        del child2.fitness.values
                    
                    offspring.append(child1)
                    if len(offspring) < self.population_size - self.elite_size:
                        offspring.append(child2)
                
                # Мутация
                for mutant in offspring:
                    if random.random() < self.mutation_prob:
                        self.toolbox.mutate(mutant)
                        del mutant.fitness.values
                
                # Оценка новых особей
                invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                fitnesses = list(self.toolbox.map(self.toolbox.evaluate, invalid_ind))
                for ind, fit in zip(invalid_ind, fitnesses):
                    ind.fitness.values = fit
                
                # Формируем новое поколение
                population = elite + offspring[:self.population_size - self.elite_size]
        
        # Финальная сортировка
        population.sort(key=lambda x: x.fitness.values[0], reverse=True)
        final_best = population[0]
        final_best_score = final_best.fitness.values[0]
        final_best_params = self._individual_to_params(final_best)
        
        if final_best_score > best_score:
            best_score = final_best_score
            best_params = final_best_params
        
        # Очищаем in-memory кэш после завершения оптимизации
        self._memory_cache.clear()
        
        log.info("Генетическая оптимизация завершена. Лучший результат: %s = %.4f", optimization_metric, best_score)
        log.info("Лучшие параметры: %s", best_params)
        
        return OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            all_results=all_results,
            optimization_metric=optimization_metric,
        )

