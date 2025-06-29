# 🚀 Руководство по развертыванию VendHub

Это пошаговое руководство поможет вам развернуть VendHub с минимальными затратами (до $300/месяц).

## 📋 Содержание
1. [Подготовка](#подготовка)
2. [База данных (Supabase)](#база-данных-supabase)
3. [Redis (Upstash)](#redis-upstash)
4. [Backend (Railway)](#backend-railway)
5. [Telegram Bot](#telegram-bot)
6. [Мониторинг](#мониторинг)
7. [Обновление](#обновление)

##  Подготовка

### Требования:
- Git
- GitHub аккаунт
- Telegram аккаунт
- Email для регистрации сервисов

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/vendhub.git
cd vendhub
```

### 2. Создание .env файла
```bash
cp .env.example .env
```

##  База данных (Supabase)

### 1. Регистрация на Supabase
1. Перейдите на [supabase.com](https://supabase.com)
2. Создайте аккаунт (можно через GitHub)
3. Создайте новый проект:
   - Project Name: `vendhub`
   - Database Password: сохраните надежно!
   - Region: выберите ближайший

### 2. Получение credentials
В настройках проекта найдите:
- Database URL (Settings  Database  Connection string)
- Anon Key (Settings  API)

### 3. Обновление .env
```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres
SUPABASE_URL=https://[YOUR-PROJECT].supabase.co
SUPABASE_KEY=[YOUR-ANON-KEY]
```

### 4. Инициализация БД
```bash
# Локально
python -m alembic upgrade head

# Или через SQL Editor в Supabase
# Скопируйте содержимое из migrations/
```

##  Redis (Upstash)

### 1. Регистрация на Upstash
1. Перейдите на [upstash.com](https://upstash.com)
2. Создайте аккаунт
3. Create Database:
   - Name: `vendhub-redis`
   - Region: выберите ближайший
   - Type: Regional (не Global)

### 2. Получение credentials
- Redis URL из Dashboard
- Включите Eviction если нужно

### 3. Обновление .env
```env
REDIS_URL=rediss://default:[YOUR-PASSWORD]@[YOUR-ENDPOINT].upstash.io:6379
```

##  Backend (Railway)

### 1. Подготовка GitHub
1. Создайте репозиторий на GitHub
2. Загрузите код:
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Развертывание на Railway
1. Перейдите на [railway.app](https://railway.app)
2. Войдите через GitHub
3. New Project  Deploy from GitHub repo
4. Выберите ваш репозиторий

### 3. Настройка переменных
В Railway dashboard:
1. Перейдите в Variables
2. Add Variable  Bulk Import from .env
3. Вставьте содержимое вашего .env файла
4. Важно изменить:
```env
ENVIRONMENT=production
DEBUG=False
USE_WEBHOOK=True
BOT_WEBHOOK_URL=https://[YOUR-APP].railway.app/webhook
```

### 4. Настройка домена
1. Settings  Domains
2. Generate Domain или добавьте свой

### 5. Проверка деплоя
```bash
curl https://[YOUR-APP].railway.app/health
```

##  Telegram Bot

### 1. Создание бота
1. Откройте [@BotFather](https://t.me/botfather)
2. Отправьте `/newbot`
3. Выберите имя и username
4. Сохраните токен

### 2. Настройка webhook
```bash
# Установка webhook
curl -X POST https://api.telegram.org/bot[YOUR-BOT-TOKEN]/setWebhook \
  -H "Content-Type: application/json" \
  -d '{"url": "https://[YOUR-APP].railway.app/webhook"}'
```

### 3. Команды бота
В BotFather отправьте `/setcommands` и вставьте:
```
start -  Начать работу
menu -  Главное меню
help -  Помощь
profile -  Мой профиль
tasks -  Мои задачи
stats -  Статистика
settings -  Настройки
cancel -  Отмена
```

##  Мониторинг

### 1. Railway Metrics
- Встроенный мониторинг в Railway Dashboard
- Логи в реальном времени

### 2. Настройка алертов
В .env добавьте админов:
```env
BOT_ADMIN_IDS=123456789,987654321
```

### 3. Бэкапы БД
Supabase автоматически делает бэкапы на бесплатном плане

##  Обновление

### 1. Через GitHub
```bash
git add .
git commit -m "Update: description"
git push origin main
```

Railway автоматически задеплоит изменения

### 2. Миграции БД
```bash
# Создание новой миграции
alembic revision --autogenerate -m "description"

# Применение
alembic upgrade head
```

##  Troubleshooting

### Проблема: База данных не подключается
- Проверьте DATABASE_URL
- Убедитесь что IP не заблокирован в Supabase

### Проблема: Бот не отвечает
- Проверьте логи в Railway
- Проверьте webhook: `https://api.telegram.org/bot[TOKEN]/getWebhookInfo`

### Проблема: Redis ошибки
- Проверьте лимиты Upstash
- Можно временно отключить: удалите REDIS_URL

##  Оптимизация расходов

### Текущие расходы:
- Railway: $0-5/месяц (Hobby план)
- Supabase: $0 (Free tier)
- Upstash: $0 (Free tier)
- **Итого: $0-5/месяц**

### При росте:
1. **Railway  $20/месяц** (Pro план)
2. **Supabase  $25/месяц** (Pro план)
3. **Upstash  $10/месяц** (Pay as you go)

##  Безопасность в продакшене

### 1. Обязательные шаги:
```env
# Сгенерируйте новые ключи!
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### 2. Rate Limiting
```env
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

##  Масштабирование

### Этап 1: MVP (0-100 автоматов)
- Текущая конфигурация
- Расходы: $0-5/месяц

### Этап 2: Рост (100-500 автоматов)
- Railway Pro + Supabase Pro
- Расходы: $50-100/месяц

### Этап 3: Масштаб (500+ автоматов)
- Переход на AWS/GCP
- Расходы: $200-300/месяц

##  Готово!

Ваш VendHub развернут и готов к работе! 

### Первые шаги:
1. Отправьте `/start` боту
2. Создайте первого админа
3. Настройте роли и права
4. Добавьте первый автомат

### Полезные команды:
```bash
# Создание админа
railway run python scripts/create_admin.py

# Seed данные
railway run python scripts/seed_data.py
```

Удачи с вашим вендинговым бизнесом! 
