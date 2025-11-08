#!/bin/bash
# Скрипт для проверки готовности к добавлению данных через Git LFS

echo "="*60
echo "🔍 Проверка готовности Git LFS"
echo "="*60

# Проверка Git LFS
if command -v git-lfs &> /dev/null; then
    echo "✅ Git LFS установлен: $(git lfs version | head -1)"
else
    echo "❌ Git LFS не установлен"
    echo "   Установите: brew install git-lfs (macOS) или apt-get install git-lfs (Linux)"
    exit 1
fi

# Проверка инициализации
if git lfs env | grep -q "git config filter.lfs"; then
    echo "✅ Git LFS инициализирован"
else
    echo "⚠️  Git LFS не инициализирован, выполните: git lfs install"
fi

# Проверка .gitattributes
if [ -f .gitattributes ]; then
    echo "✅ .gitattributes существует"
    if grep -q "*.parquet" .gitattributes; then
        echo "✅ Отслеживание *.parquet настроено"
    else
        echo "⚠️  Отслеживание *.parquet не настроено"
    fi
else
    echo "❌ .gitattributes не найден"
    exit 1
fi

# Проверка данных
echo ""
echo "📁 Проверка данных:"
if [ -d "data/v1/curated/ctrader" ]; then
    parquet_count=$(find data/v1/curated/ctrader -name "*.parquet" 2>/dev/null | wc -l)
    if [ "$parquet_count" -gt 0 ]; then
        echo "✅ Найдено $parquet_count parquet файлов в data/v1/curated/ctrader/"
        echo ""
        echo "📋 Следующие шаги:"
        echo "1. git add data/v1/curated/ctrader/*.parquet"
        echo "2. git commit -m 'Add forex data files via Git LFS'"
        echo "3. git push"
    else
        echo "⚠️  Папка data/v1/curated/ctrader/ существует, но файлов нет"
        echo ""
        echo "💡 Скопируйте данные:"
        echo "   cp '/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader'/*.parquet data/v1/curated/ctrader/"
    fi
else
    echo "⚠️  Папка data/v1/curated/ctrader/ не существует"
    echo ""
    echo "💡 Создайте папку и скопируйте данные:"
    echo "   mkdir -p data/v1/curated/ctrader"
    echo "   cp '/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader'/*.parquet data/v1/curated/ctrader/"
fi

echo ""
echo "="*60
