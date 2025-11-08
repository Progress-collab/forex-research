# Установка Git LFS на Mac и добавление данных

## Шаг 1: Установить Git LFS

На вашем Mac выполните:

```bash
# Установить через Homebrew (если установлен)
brew install git-lfs

# Или скачать с официального сайта:
# https://git-lfs.github.com/
```

После установки проверьте:

```bash
git-lfs version
```

Должно показать версию, например: `git-lfs/3.x.x`

## Шаг 2: Инициализировать Git LFS

```bash
# Инициализировать Git LFS
git lfs install

# Должно показать: "Git LFS initialized."
```

## Шаг 3: Добавить данные в Git LFS

```bash
# Добавить данные в Git LFS
git add data/v1/curated/ctrader/*.parquet

# Проверить что файлы будут через LFS (должны показаться 12 файлов)
git lfs ls-files
```

## Шаг 4: Закоммитить и запушить

```bash
# Закоммитить
git commit -m "Add forex data files via Git LFS"

# Запушить (данные будут загружены через LFS)
git push
```

## Если Homebrew не установлен:

Установите Homebrew сначала:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Затем установите Git LFS:

```bash
brew install git-lfs
```

## Альтернатива: Скачать вручную

1. Перейдите на https://git-lfs.github.com/
2. Скачайте установщик для macOS
3. Установите
4. Выполните `git lfs install`

После установки Git LFS выполните шаги 2-4 выше!
