# ✅ Данные найдены! Добавление в Git LFS

Вы нашли 12 parquet файлов в проекте! Теперь нужно добавить их в Git LFS.

## Выполните эти команды на вашем Mac:

```bash
# 1. Убедиться что Git LFS установлен и инициализирован
git lfs install

# 2. Добавить данные в Git LFS
git add data/v1/curated/ctrader/*.parquet

# 3. Проверить что файлы будут через LFS
git lfs ls-files

# 4. Закоммитить
git commit -m "Add forex data files via Git LFS"

# 5. Запушить (данные будут загружены через LFS)
git push
```

## Проверка после push:

```bash
# Проверить что данные через LFS
git lfs ls-files

# Запустить тест стратегии
python3 scripts/check_and_test_momentum.py
```

## Что будет:

После выполнения этих команд:
- ✅ Данные будут в Git через LFS
- ✅ Данные будут доступны в облаке
- ✅ Можно будет работать с данными в любом окружении

Выполните команды выше на вашем Mac!
