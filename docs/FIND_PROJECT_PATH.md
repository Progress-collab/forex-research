# ⚠️ ВАЖНО: Разница между локальным Mac и удаленным окружением

## Проблема

`/workspace` - это путь в **удаленном окружении Cursor** (Linux), а не на вашем Mac!

## Решение: Найти правильный путь к проекту

### Вариант 1: Через Cursor (рекомендуется)

Если проект открыт в Cursor, используйте встроенный терминал Cursor:
1. Откройте терминал в Cursor (Terminal → New Terminal)
2. Там уже будет правильный путь к проекту
3. Выполните команды там

### Вариант 2: Найти путь к проекту на Mac

Проект скорее всего находится в одном из этих мест:

```bash
# Проверьте эти пути:
ls ~/Yandex.Disk-eglazejkin.localized/Cursor_happy/
ls ~/Documents/Cursor/
ls ~/Projects/
ls ~/forex-research/
```

Или найдите через Finder:
1. Откройте Finder
2. Найдите папку с проектом (возможно называется `forex-research`)
3. Перетащите папку в терминал чтобы увидеть путь

### Вариант 3: Использовать абсолютный путь к данным

Если не можете найти проект, можно скопировать данные напрямую:

```bash
# Создать временную папку для проекта
mkdir -p ~/temp-forex-project/data/v1/curated/ctrader

# Скопировать данные
cp "/Users/evgenyglazeykin/Yandex.Disk-eglazejkin.localized/Cursor_happy/data/v1/curated/ctrader"/*.parquet ~/temp-forex-project/data/v1/curated/ctrader/

# Затем в Cursor скопировать из ~/temp-forex-project/data в проект
```

## Рекомендация

**Используйте терминал Cursor** - там уже будет правильный путь к проекту!

1. Откройте Cursor
2. Откройте проект (если еще не открыт)
3. Откройте терминал в Cursor (Terminal → New Terminal)
4. Выполните там: `bash scripts/do_steps_2_3_4.sh`
