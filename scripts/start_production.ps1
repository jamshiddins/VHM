# start_production.ps1
Write-Host "Starting VendHub Production..." -ForegroundColor Cyan

# Переход в директорию проекта
Set-Location C:\VendHub

# Остановка старых контейнеров
docker-compose -f docker-compose.production.yml down

# Сборка и запуск
docker-compose -f docker-compose.production.yml up -d --build

# Проверка статуса
Start-Sleep -Seconds 10
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`nVendHub started successfully!" -ForegroundColor Green
Write-Host "API: https://api.vendhub.uz" -ForegroundColor Yellow
Write-Host "Logs: docker logs vendhub_backend_prod" -ForegroundColor Yellow
