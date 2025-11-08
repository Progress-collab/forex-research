# Решение: Данные в облаке

## 🎯 Проблема
Без данных в облаке нельзя работать, но обычный Git не подходит для больших файлов.

## ✅ Решение: Git LFS (Large File Storage)

Git LFS позволяет хранить большие файлы в Git без замедления репозитория.

### Быстрая настройка:

```bash
# 1. Установить Git LFS (если еще не установлен)
brew install git-lfs  # macOS
# или
sudo apt-get install git-lfs  # Linux

# 2. Инициализировать Git LFS
git lfs install

# 3. Настроить отслеживание parquet файлов
git lfs track "*.parquet"
git lfs track "data/v1/curated/ctrader/*.parquet"

# 4. Добавить .gitattributes
git add .gitattributes
git commit -m "Configure Git LFS for data files"

# 5. Скопировать данные
cp "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"/*.parquet data/v1/curated/ctrader/

# 6. Добавить данные в git (через LFS)
git add data/v1/curated/ctrader/*.parquet
git commit -m "Add forex data files via Git LFS"
git push
```

После этого данные будут доступны в облаке! 🎉

## Альтернатива: Автоматическая загрузка при деплое

Если Git LFS не подходит, можно использовать скрипт `scripts/download_data_on_deploy.py` который:
1. Проверяет наличие данных
2. Если данных нет - скачивает через cTrader API
3. Сохраняет в `data/v1/curated/ctrader/`

Требует настройки переменных окружения для API.
