# scripts/run-bot-setup.ps1
# PowerShell скрипт для запуска настройки Telegram бота

Write-Host " Запуск настройки Telegram бота..." -ForegroundColor Green

# Проверка наличия Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python не установлен!" -ForegroundColor Red
    Write-Host "Установите Python 3.11+ и повторите попытку" -ForegroundColor Yellow
    exit 1
}

# Проверка наличия .env файла
if (-not (Test-Path ".env")) {
    Write-Host "❌ Файл .env не найден!" -ForegroundColor Red
    Write-Host "Создайте .env файл с BOT_TOKEN" -ForegroundColor Yellow
    exit 1
}

# Проверка наличия BOT_TOKEN в .env
$envContent = Get-Content .env
if (-not ($envContent -match "BOT_TOKEN=.+")) {
    Write-Host "⚠ BOT_TOKEN не найден в .env файле!" -ForegroundColor Yellow
    Write-Host "Добавьте строку: BOT_TOKEN=your-bot-token" -ForegroundColor Yellow
}

# Активация виртуального окружения если существует
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "Активация виртуального окружения..." -ForegroundColor Gray
    & "venv\Scripts\activate.ps1"
}

# Запуск скрипта настройки
Write-Host "Запуск скрипта настройки..." -ForegroundColor Gray
python scripts\setup_telegram_bot.py

Write-Host "`n Готово!" -ForegroundColor Green
