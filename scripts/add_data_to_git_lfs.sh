#!/bin/bash
# Проверка и добавление данных в Git LFS (если данные уже в проекте)

set -e

echo "="*60
echo "🔍 Проверка данных и добавление в Git LFS"
echo "="*60

# Определяем текущую директорию проекта
if [ -f "pyproject.toml" ] && [ -d "src" ]; then
    PROJECT_DIR=$(pwd)
    echo "✅ Проект найден в: $PROJECT_DIR"
else
    echo "⚠️  Запустите скрипт из корня проекта (где есть pyproject.toml)"
    exit 1
fi

DATA_DIR="$PROJECT_DIR/data/v1/curated/ctrader"

# Проверяем наличие данных
echo ""
echo "📁 Проверка данных в $DATA_DIR..."

if [ ! -d "$DATA_DIR" ]; then
    echo "❌ Папка не существует"
    exit 1
fi

PARQUET_FILES=$(find "$DATA_DIR" -name "*.parquet" 2>/dev/null)
PARQUET_COUNT=$(echo "$PARQUET_FILES" | grep -c ".parquet" || echo "0")

if [ "$PARQUET_COUNT" -eq 0 ]; then
    echo "⚠️  Parquet файлы не найдены"
    echo ""
    echo "💡 Скопируйте данные:"
    echo "   cp '/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader'/*.parquet $DATA_DIR/"
    exit 1
fi

echo "✅ Найдено $PARQUET_COUNT parquet файлов"
echo ""
echo "📋 Файлы:"
ls -lh "$DATA_DIR"/*.parquet | head -5

# Проверяем Git LFS
echo ""
echo "🔍 Проверка Git LFS..."
if ! command -v git-lfs &> /dev/null; then
    echo "❌ Git LFS не установлен"
    echo "   Установите: brew install git-lfs"
    exit 1
fi

git lfs install > /dev/null 2>&1 || true

# Добавляем в Git LFS
echo ""
echo "📋 Добавление данных в Git LFS..."
git add "$DATA_DIR"/*.parquet

echo ""
echo "📊 Файлы через Git LFS:"
git lfs ls-files

echo ""
echo "="*60
echo "✅ Готово!"
echo "="*60
echo ""
echo "📋 Следующие шаги:"
echo "1. git commit -m 'Add forex data files via Git LFS'"
echo "2. git push"
echo ""
