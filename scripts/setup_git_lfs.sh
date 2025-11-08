#!/bin/bash
# Скрипт для настройки Git LFS и добавления данных

echo "🔧 Настройка Git LFS для данных..."

# Проверяем установлен ли Git LFS
if ! command -v git-lfs &> /dev/null; then
    echo "⚠️  Git LFS не установлен!"
    echo "Установите:"
    echo "  macOS: brew install git-lfs"
    echo "  Linux: sudo apt-get install git-lfs"
    echo "  Windows: https://git-lfs.github.com/"
    exit 1
fi

# Инициализируем Git LFS
git lfs install

# Настраиваем отслеживание parquet файлов
echo "📦 Настройка отслеживания .parquet файлов..."
git lfs track "*.parquet"
git lfs track "data/v1/curated/ctrader/*.parquet"

# Добавляем .gitattributes
git add .gitattributes

echo "✅ Git LFS настроен!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Скопируйте данные в data/v1/curated/ctrader/"
echo "2. git add data/v1/curated/ctrader/*.parquet"
echo "3. git commit -m 'Add data files via Git LFS'"
echo "4. git push"
