# Скрипт для настройки PowerShell профиля для поддержки UTF-8
# Запустите этот скрипт один раз для постоянной настройки UTF-8 в PowerShell

Write-Host "Настройка PowerShell профиля для поддержки UTF-8..." -ForegroundColor Cyan

# Определяем путь к профилю PowerShell
$profilePath = $PROFILE.CurrentUserAllHosts

# Проверяем, существует ли профиль
if (-not (Test-Path $profilePath)) {
    Write-Host "Создание профиля PowerShell..." -ForegroundColor Yellow
    $profileDir = Split-Path $profilePath -Parent
    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

# Проверяем, не добавлены ли уже настройки UTF-8
$profileContent = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
$utf8Marker = "# UTF-8 encoding setup for forex-research project"

if ($profileContent -and $profileContent.Contains($utf8Marker)) {
    Write-Host "Настройки UTF-8 уже присутствуют в профиле." -ForegroundColor Green
    Write-Host "Путь к профилю: $profilePath" -ForegroundColor Gray
    exit 0
}

# Добавляем настройки UTF-8 в профиль
Write-Host "Добавление настроек UTF-8 в профиль..." -ForegroundColor Yellow

$utf8Config = @"

# UTF-8 encoding setup for forex-research project
# Автоматически устанавливает UTF-8 кодировку при запуске PowerShell
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"

"@

# Добавляем в конец файла профиля
Add-Content -Path $profilePath -Value $utf8Config

Write-Host "`nНастройки UTF-8 успешно добавлены в профиль PowerShell!" -ForegroundColor Green
Write-Host "Путь к профилю: $profilePath" -ForegroundColor Gray
Write-Host "`nДля применения изменений:" -ForegroundColor Yellow
Write-Host "  1. Перезапустите PowerShell, или" -ForegroundColor White
Write-Host "  2. Выполните команду: . `$PROFILE" -ForegroundColor White
Write-Host "`nТеперь UTF-8 будет автоматически настроен при каждом запуске PowerShell." -ForegroundColor Cyan

