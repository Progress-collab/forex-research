# Решение: Данные в облаке через Git LFS

## Проблема
Без данных в облаке нельзя работать, но обычный Git не подходит для больших файлов.

## Решение: Git LFS (Large File Storage)

Git LFS позволяет хранить большие файлы в Git без замедления репозитория.

### Шаг 1: Установка Git LFS

```bash
# macOS
brew install git-lfs

# Linux
sudo apt-get install git-lfs

# Windows
# Скачайте с https://git-lfs.github.com/
```

### Шаг 2: Настройка Git LFS

```bash
# Инициализация
git lfs install

# Настройка отслеживания parquet файлов
git lfs track "*.parquet"
git lfs track "data/v1/curated/ctrader/*.parquet"

# Добавить .gitattributes в git
git add .gitattributes
git commit -m "Configure Git LFS for data files"
```

### Шаг 3: Добавление данных

```bash
# Скопировать данные из локальной папки
cp "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"/*.parquet data/v1/curated/ctrader/

# Добавить в git (через LFS)
git add data/v1/curated/ctrader/*.parquet

# Закоммитить
git commit -m "Add forex data files via Git LFS"

# Запушить (данные будут загружены через LFS)
git push
```

## Альтернативное решение: Автоматическая загрузка данных

Если Git LFS не подходит, можно настроить автоматическую загрузку данных при деплое:

### Вариант A: Через API при деплое

Создать скрипт `scripts/download_data_on_deploy.sh` который:
1. Проверяет наличие данных
2. Если данных нет - скачивает через cTrader API
3. Сохраняет в `data/v1/curated/ctrader/`

### Вариант B: Внешнее хранилище

Использовать Google Cloud Storage / AWS S3:
1. Загрузить данные в облачное хранилище
2. При деплое скачивать данные оттуда
3. Кэшировать локально

## Рекомендация

**Используйте Git LFS** - это самое простое решение для начала работы.

### Преимущества Git LFS:
- ✅ Данные в репозитории
- ✅ Работает в облаке автоматически
- ✅ Не замедляет git операции
- ✅ Простая настройка

### Недостатки:
- ⚠️ Требует установки Git LFS
- ⚠️ GitHub имеет лимиты на LFS (1 GB бесплатно)

## Быстрый старт

```bash
# 1. Установить Git LFS (если еще не установлен)
brew install git-lfs  # или apt-get install git-lfs

# 2. Настроить
./scripts/setup_git_lfs.sh

# 3. Скопировать данные
cp "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"/*.parquet data/v1/curated/ctrader/

# 4. Добавить и закоммитить
git add data/v1/curated/ctrader/*.parquet
git commit -m "Add data files via Git LFS"
git push
```

После этого данные будут доступны в облаке!
