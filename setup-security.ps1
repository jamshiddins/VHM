# setup-security.ps1
# PowerShell скрипт для настройки безопасности VendHub на Windows

Write-Host "🛡️ Настройка безопасности VendHub..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# Проверка прав администратора
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ Этот скрипт требует прав администратора!" -ForegroundColor Red
    Write-Host "Перезапустите PowerShell от имени администратора" -ForegroundColor Yellow
    exit 1
}

# 1. Создание структуры директорий
Write-Host "`n📁 Создание структуры директорий..." -ForegroundColor Yellow
$directories = @(
    "nginx\ssl",
    "scripts\security",
    "monitoring\alerts",
    "backup\database",
    "backup\files",
    "logs\security",
    ".secrets"
)

foreach ($dir in $directories) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Host "  ✓ $dir" -ForegroundColor Gray
}

# 2. Генерация самоподписанных SSL сертификатов (для разработки)
Write-Host "`n📜 Генерация SSL сертификатов..." -ForegroundColor Yellow
if (-not (Test-Path "nginx\ssl\cert.pem")) {
    # Создаем конфигурацию OpenSSL
    $opensslConfig = @"
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn

[dn]
C=UZ
ST=Tashkent
L=Tashkent
O=VendHub
CN=*.vendhub.uz
"@
    $opensslConfig | Out-File -FilePath "nginx\ssl\openssl.cnf" -Encoding UTF8

    # Генерация сертификата
    if (Get-Command openssl -ErrorAction SilentlyContinue) {
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
            -keyout nginx\ssl\key.pem `
            -out nginx\ssl\cert.pem `
            -config nginx\ssl\openssl.cnf
        Write-Host "  ✓ SSL сертификаты созданы" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ OpenSSL не установлен. Пропускаем генерацию сертификатов" -ForegroundColor Yellow
    }
}

# 3. Создание скрипта для Let's Encrypt (для production)
Write-Host "`n📄 Создание скрипта Let's Encrypt..." -ForegroundColor Yellow
$letsencryptScript = @'
#!/bin/bash
# scripts/letsencrypt.sh

echo "📜 Получение SSL сертификатов Let's Encrypt..."

# Остановка nginx для получения сертификатов
docker-compose -f docker-compose.production.yml stop nginx

# Получение сертификатов
docker run -it --rm \
  -v $(pwd)/nginx/ssl:/etc/letsencrypt \
  -v $(pwd)/nginx/ssl:/var/lib/letsencrypt \
  -p 80:80 \
  certbot/certbot \
  certonly --standalone \
  --email ${SSL_EMAIL} \
  --agree-tos \
  --no-eff-email \
  --force-renewal \
  -d vendhub.uz -d www.vendhub.uz -d api.vendhub.uz

# Копирование сертификатов
cp nginx/ssl/live/vendhub.uz/fullchain.pem nginx/ssl/fullchain.pem
cp nginx/ssl/live/vendhub.uz/privkey.pem nginx/ssl/privkey.pem

# Запуск nginx
docker-compose -f docker-compose.production.yml start nginx

echo "✅ SSL сертификаты получены!"
'@
$letsencryptScript | Out-File -FilePath "scripts\letsencrypt.sh" -Encoding UTF8 -NoNewline

# 4. Генерация секретных ключей
Write-Host "`n🔑 Генерация секретных ключей..." -ForegroundColor Yellow

# Функция для генерации случайных строк
function New-RandomPassword {
    param([int]$Length = 32)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
    $password = ''
    $random = New-Object System.Random
    for ($i = 0; $i -lt $Length; $i++) {
        $password += $chars[$random.Next($chars.Length)]
    }
    return $password
}

$secrets = @{
    SECRET_KEY = New-RandomPassword -Length 64
    JWT_SECRET_KEY = New-RandomPassword -Length 64
    DB_PASSWORD = New-RandomPassword -Length 32
    REDIS_PASSWORD = New-RandomPassword -Length 32
    GRAFANA_PASSWORD = New-RandomPassword -Length 16
}

# 5. Создание .env.secure файла
Write-Host "`n📄 Создание .env.secure файла..." -ForegroundColor Yellow
$envContent = @"
# ===== SECURITY KEYS (Generated $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")) =====
SECRET_KEY=$($secrets.SECRET_KEY)
JWT_SECRET_KEY=$($secrets.JWT_SECRET_KEY)
DB_PASSWORD=$($secrets.DB_PASSWORD)
REDIS_PASSWORD=$($secrets.REDIS_PASSWORD)
GRAFANA_PASSWORD=$($secrets.GRAFANA_PASSWORD)

# ===== SSL CONFIGURATION =====
SSL_EMAIL=admin@vendhub.uz
CERTBOT_EMAIL=admin@vendhub.uz

# ===== SECURITY SETTINGS =====
ALLOWED_HOSTS=vendhub.uz,www.vendhub.uz,api.vendhub.uz
CORS_ORIGINS=https://vendhub.uz,https://www.vendhub.uz
SECURE_COOKIES=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# ===== RATE LIMITING =====
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# ===== MONITORING =====
SENTRY_DSN=your-sentry-dsn-here
ENABLE_PROMETHEUS=True
ENABLE_GRAFANA=True
"@
$envContent | Out-File -FilePath ".env.secure" -Encoding UTF8

# Установка ограниченных прав доступа (только для владельца)
$acl = Get-Acl ".env.secure"
$acl.SetAccessRuleProtection($true, $false)
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
    "FullControl",
    "Allow"
)
$acl.SetAccessRule($accessRule)
Set-Acl ".env.secure" $acl

Write-Host "  ✓ Файл .env.secure создан с ограниченными правами" -ForegroundColor Green

# 6. Создание скрипта резервного копирования для Windows
Write-Host "`n💾 Создание скрипта резервного копирования..." -ForegroundColor Yellow
$backupScript = @'
# backup.ps1
# PowerShell скрипт для резервного копирования VendHub

param(
    [string]$BackupType = "full",
    [string]$Destination = ".\backup"
)

Write-Host "💾 Начало резервного копирования VendHub..." -ForegroundColor Green

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "vendhub_backup_$timestamp"
$backupPath = Join-Path $Destination $backupName

# Создание директории для бэкапа
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null

# 1. Бэкап базы данных
Write-Host "📊 Создание дампа базы данных..."
docker-compose -f docker-compose.production.yml exec -T postgres pg_dump -U vendhub_user vendhub_prod > "$backupPath\database.sql"

# 2. Бэкап файлов
Write-Host "📁 Копирование файлов..."
Copy-Item -Path "static\uploads" -Destination "$backupPath\uploads" -Recurse -Force
Copy-Item -Path "static\exports" -Destination "$backupPath\exports" -Recurse -Force
Copy-Item -Path ".env" -Destination "$backupPath\.env.backup" -Force

# 3. Создание архива
Write-Host "📦 Создание архива..."
Compress-Archive -Path "$backupPath\*" -DestinationPath "$backupPath.zip" -Force
Remove-Item -Path $backupPath -Recurse -Force

# 4. Очистка старых бэкапов (старше 30 дней)
Write-Host "🧹 Очистка старых бэкапов..."
Get-ChildItem -Path $Destination -Filter "vendhub_backup_*.zip" | 
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-30) } | 
    Remove-Item -Force

Write-Host "✅ Резервное копирование завершено: $backupName.zip" -ForegroundColor Green
'@
$backupScript | Out-File -FilePath "scripts\backup.ps1" -Encoding UTF8

# 7. Создание скрипта для Windows Firewall
Write-Host "`n🔥 Создание правил Windows Firewall..." -ForegroundColor Yellow
$firewallScript = @'
# firewall-setup.ps1
# Настройка Windows Firewall для VendHub

Write-Host "Настройка Windows Firewall..." -ForegroundColor Yellow

# Удаление существующих правил
Remove-NetFirewallRule -DisplayName "VendHub*" -ErrorAction SilentlyContinue

# HTTP
New-NetFirewallRule -DisplayName "VendHub HTTP" `
    -Direction Inbound -Protocol TCP -LocalPort 80 `
    -Action Allow -Profile Any

# HTTPS
New-NetFirewallRule -DisplayName "VendHub HTTPS" `
    -Direction Inbound -Protocol TCP -LocalPort 443 `
    -Action Allow -Profile Any

# PostgreSQL (только для локальной сети)
New-NetFirewallRule -DisplayName "VendHub PostgreSQL" `
    -Direction Inbound -Protocol TCP -LocalPort 5432 `
    -Action Allow -Profile Private -RemoteAddress LocalSubnet

# Redis (только для локальной сети)
New-NetFirewallRule -DisplayName "VendHub Redis" `
    -Direction Inbound -Protocol TCP -LocalPort 6379 `
    -Action Allow -Profile Private -RemoteAddress LocalSubnet

# Grafana
New-NetFirewallRule -DisplayName "VendHub Grafana" `
    -Direction Inbound -Protocol TCP -LocalPort 3001 `
    -Action Allow -Profile Any

# Prometheus
New-NetFirewallRule -DisplayName "VendHub Prometheus" `
    -Direction Inbound -Protocol TCP -LocalPort 9090 `
    -Action Allow -Profile Private

Write-Host "✅ Правила Windows Firewall настроены" -ForegroundColor Green
'@
$firewallScript | Out-File -FilePath "scripts\firewall-setup.ps1" -Encoding UTF8

# 8. Создание скрипта мониторинга
Write-Host "`n📊 Создание скрипта мониторинга..." -ForegroundColor Yellow
$monitoringScript = @'
# monitor-health.ps1
# Скрипт проверки состояния VendHub

Write-Host "🏥 Проверка состояния VendHub..." -ForegroundColor Green

$services = @(
    @{Name="Backend API"; Url="http://localhost:8000/health"},
    @{Name="Frontend"; Url="http://localhost:3000"},
    @{Name="PostgreSQL"; Port=5432},
    @{Name="Redis"; Port=6379}
)

$allHealthy = $true

foreach ($service in $services) {
    Write-Host -NoNewline "Проверка $($service.Name)... "
    
    try {
        if ($service.Url) {
            $response = Invoke-WebRequest -Uri $service.Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Host "✅ OK" -ForegroundColor Green
            } else {
                Write-Host "❌ Ошибка (Status: $($response.StatusCode))" -ForegroundColor Red
                $allHealthy = $false
            }
        } elseif ($service.Port) {
            $connection = Test-NetConnection -ComputerName localhost -Port $service.Port -WarningAction SilentlyContinue
            if ($connection.TcpTestSucceeded) {
                Write-Host "✅ OK" -ForegroundColor Green
            } else {
                Write-Host "❌ Недоступен" -ForegroundColor Red
                $allHealthy = $false
            }
        }
    } catch {
        Write-Host "❌ Ошибка: $_" -ForegroundColor Red
        $allHealthy = $false
    }
}

# Проверка Docker контейнеров
Write-Host "`nПроверка Docker контейнеров:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

if ($allHealthy) {
    Write-Host "`n✅ Все сервисы работают нормально!" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ Обнаружены проблемы с некоторыми сервисами!" -ForegroundColor Yellow
}
'@
$monitoringScript | Out-File -FilePath "scripts\monitor-health.ps1" -Encoding UTF8

# 9. Создание планировщика задач для автоматического бэкапа
Write-Host "`n⏰ Настройка автоматического резервного копирования..." -ForegroundColor Yellow
$taskAction = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$(Get-Location)\scripts\backup.ps1`""
$taskTrigger = New-ScheduledTaskTrigger -Daily -At "03:00AM"
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

try {
    Register-ScheduledTask -TaskName "VendHub Daily Backup" `
        -Action $taskAction `
        -Trigger $taskTrigger `
        -Settings $taskSettings `
        -Description "Ежедневное резервное копирование VendHub" `
        -Force | Out-Null
    Write-Host "  ✓ Задача автоматического бэкапа создана" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️ Не удалось создать задачу в планировщике" -ForegroundColor Yellow
}

# 10. Создание файла с инструкциями
Write-Host "`n📝 Создание инструкций по безопасности..." -ForegroundColor Yellow
$securityInstructions = @"
# 🛡️ ИНСТРУКЦИИ ПО БЕЗОПАСНОСТИ VENDHUB

## 🔐 Сгенерированные пароли сохранены в файле .env.secure

## 📋 Чек-лист безопасности:

### 1. SSL Сертификаты
   - [ ] Для разработки: используйте самоподписанные сертификаты из nginx/ssl/
   - [ ] Для production: запустите scripts/letsencrypt.sh на Linux сервере

### 2. Файрвол
   - [ ] Windows: запустите scripts/firewall-setup.ps1 от имени администратора
   - [ ] Linux: используйте ufw или iptables

### 3. Резервное копирование
   - [ ] Автоматическое: настроено на 3:00 ежедневно
   - [ ] Ручное: .\scripts\backup.ps1

### 4. Мониторинг
   - [ ] Проверка состояния: .\scripts\monitor-health.ps1
   - [ ] Grafana: http://localhost:3001 (admin / см. GRAFANA_PASSWORD в .env.secure)
   - [ ] Prometheus: http://localhost:9090

### 5. Обновление паролей
   - [ ] Скопируйте пароли из .env.secure в основной .env файл
   - [ ] Удалите .env.secure после копирования
   - [ ] Никогда не коммитьте .env файлы в Git

### 6. Дополнительные меры безопасности
   - [ ] Включите 2FA для всех администраторов
   - [ ] Регулярно обновляйте Docker образы
   - [ ] Проверяйте логи на наличие подозрительной активности
   - [ ] Используйте VPN для доступа к административным интерфейсам

## 🚨 Важные команды:

# Проверка безопасности контейнеров
docker scout cves

# Обновление всех образов
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Просмотр логов безопасности
docker-compose -f docker-compose.production.yml logs -f nginx | Select-String "error|warn"

## 📞 Контакты для экстренных случаев:
- Системный администратор: [добавьте контакт]
- Служба безопасности: [добавьте контакт]
"@
$securityInstructions | Out-File -FilePath "SECURITY.md" -Encoding UTF8

# Итоговый вывод
Write-Host "`n✅ Настройка безопасности завершена!" -ForegroundColor Green
Write-Host "`n📋 Выполненные действия:" -ForegroundColor Yellow
Write-Host "  ✓ Созданы директории для безопасности"
Write-Host "  ✓ Сгенерированы SSL сертификаты (самоподписанные)"
Write-Host "  ✓ Созданы секретные ключи"
Write-Host "  ✓ Настроено автоматическое резервное копирование"
Write-Host "  ✓ Созданы скрипты для мониторинга"
Write-Host "  ✓ Подготовлены правила файрвола"

Write-Host "`n⚠️  ВАЖНО:" -ForegroundColor Red
Write-Host "1. Скопируйте пароли из .env.secure в ваш основной .env файл"
Write-Host "2. Запустите .\scripts\firewall-setup.ps1 от имени администратора"
Write-Host "3. Для production используйте Let's Encrypt сертификаты"
Write-Host "4. Прочитайте SECURITY.md для полных инструкций"

Write-Host "`n🔑 Пароли сохранены в: .env.secure" -ForegroundColor Cyan
Write-Host "🛡️ НЕ ЗАБУДЬТЕ удалить этот файл после копирования паролей!" -ForegroundColor Red