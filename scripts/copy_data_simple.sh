#!/bin/bash
# Упрощенный скрипт - работает из любой директории
# Копирует данные и показывает что делать дальше

set -e

echo "="*60
echo "📋 Копирование данных для Git LFS"
echo "="*60

# Определяем текущую директорию проекта
# Если скрипт запущен из корня проекта, используем его
# Иначе пытаемся найти проект
if [ -f "pyproject.toml" ] && [ -d "src" ]; then
    PROJECT_DIR=$(pwd)
    echo "✅ Проект найден в: $PROJECT_DIR"
else
    echo "⚠️  Запустите скрипт из корня проекта (где есть pyproject.toml)"
    echo "Или укажите путь к проекту:"
    echo "  bash $0 /path/to/project"
    exit 1
fi

# Если передан путь к проекту как аргумент
if [ -n "$1" ]; then
    PROJECT_DIR="$1"
    cd "$PROJECT_DIR"
fi

SOURCE_DIR="/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"
TARGET_DIR="$PROJECT_DIR/data/v1/curated/ctrader"

echo ""
echo "📋 Шаг 1: Копирование данных..."
echo ""

# Проверяем существование исходной папки
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Исходная папка не найдена: $SOURCE_DIR"
    echo ""
    echo "💡 Проверьте путь к данным или скопируйте вручную:"
    echo "   mkdir -p $TARGET_DIR"
    echo "   cp <путь_к_данным>/*.parquet $TARGET_DIR/"
    exit 1
fi

# Создаем целевую директорию
mkdir -p "$TARGET_DIR"

# Копируем данные
echo "🔄 Копирование файлов из $SOURCE_DIR..."
cp "$SOURCE_DIR"/*.parquet "$TARGET_DIR/" 2>/dev/null || {
    echo "⚠️  Ошибка при копировании. Проверьте права доступа."
    exit 1
}

# Проверяем что файлы скопированы
PARQUET_COUNT=$(find "$TARGET_DIR" -name "*.parquet" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PARQUET_COUNT" -eq 0 ]; then
    echo "❌ Файлы не скопированы"
    exit 1
fi

echo "✅ Скопировано $PARQUET_COUNT файлов"
ls -lh "$TARGET_DIR"/*.parquet | head -5

# Шаг 2: Инструкции для Git LFS
echo ""
echo "="*60
echo "📋 Шаг 2: Добавление в Git LFS"
echo "="*60
echo ""
echo "Выполните следующие команды:"
echo ""
echo "cd $PROJECT_DIR"
echo "git add data/v1/curated/ctrader/*.parquet"
echo "git lfs ls-files  # Проверить что файлы через LFS"
echo "git commit -m 'Add forex data files via Git LFS'"
echo "git push"
echo ""
