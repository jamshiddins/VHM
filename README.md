<<<<<<< HEAD
# VHM
=======
# 🏪 VendHub - Система управления вендинговой сетью

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)
![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue)
![License](https://img.shields.io/badge/license-MIT-green)

VendHub - современная система для управления сетью вендинговых автоматов с поддержкой инвестиций, автоматизацией процессов и детальной аналитикой.

## 🚀 Особенности

### 📊 Управление автоматами
- CRUD операции для всех сущностей
- Мониторинг состояния в реальном времени
- Геолокация и маршрутизация
- История обслуживания

### 💰 Финансовый учет
- Доходы и расходы по категориям
- Сверка платежей из 4 источников
- Себестоимость продукции
- Инкассация и остатки

### 📦 Учет остатков
- Склад, автоматы, сумки операторов
- Взвешивание и инвентаризация
- Нормативы vs фактический расход
- История движения товаров

### 👥 Роли и доступ
- Admin, Manager, Warehouse, Operator, Investor
- Гибкая система прав (RBAC)
- Персонализированные интерфейсы

### 🤖 Telegram Bot
- Красивая inline навигация
- Задачи для операторов
- Фото-отчеты
- Push-уведомления

### 💎 Модуль инвестиций
- Доли в автоматах
- История выплат
- Предложения о выкупе
- Аналитика ROI

### 📈 Отчеты и аналитика
- Excel импорт/экспорт
- Графики и дашборды
- Прогнозирование
- API для интеграций

## 🛠 Технологии

### Backend
- **FastAPI** - современный async фреймворк
- **SQLAlchemy 2.0** - ORM с поддержкой async
- **PostgreSQL** - основная БД
- **Redis** - кеширование и очереди
- **Alembic** - миграции БД

### Bot
- **Aiogram 3** - Telegram Bot framework
- **FSM** - конечные автоматы для диалогов
- **Inline keyboards** - удобная навигация

### Инфраструктура
- **Docker** - контейнеризация
- **GitHub Actions** - CI/CD
- **Railway/Render** - хостинг
- **Supabase** - managed PostgreSQL
- **Upstash** - managed Redis

## 📋 Требования

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker (опционально)

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/yourusername/vendhub.git
cd vendhub
```

### 2. Создание виртуального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка окружения
```bash
cp .env.example .env
# Отредактируйте .env файл
```

### 5. Запуск через Docker
```bash
docker-compose up -d
```

### 6. Миграции БД
```bash
alembic upgrade head
```

### 7. Создание админа
```bash
python scripts/create_admin.py
```

### 8. Запуск приложения
```bash
# API
uvicorn src.main:app --reload

# Bot
python -m src.bot.bot
```

## 📁 Структура проекта

```
vendhub/
├── src/
│   ├── api/          # API endpoints
│   ├── bot/          # Telegram bot
│   ├── core/         # Бизнес-логика
│   ├── db/           # Модели и схемы
│   ├── services/     # Сервисный слой
│   └── utils/        # Утилиты
├── migrations/       # Alembic миграции
├── static/          # Статические файлы
├── tests/           # Тесты
├── scripts/         # Вспомогательные скрипты
└── docs/            # Документация
```

## 🔧 Конфигурация

Основные настройки в `.env`:

```env
# База данных
DATABASE_URL=postgresql://user:pass@localhost/vendhub

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
BOT_TOKEN=your-bot-token

# Безопасность
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-key
```

## 📚 API Документация

После запуска доступна по адресу:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только API тесты
pytest tests/test_api/
```

## 🚀 Деплой

Подробная инструкция в [DEPLOYMENT.md](docs/DEPLOYMENT.md)

### Быстрый деплой на Railway:
1. Fork репозиторий
2. Подключите GitHub к Railway
3. Создайте новый проект из репозитория
4. Добавьте переменные окружения
5. Deploy!

## 🤝 Вклад в проект

1. Fork репозиторий
2. Создайте ветку (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📊 Roadmap

- [x] Базовая структура
- [x] Аутентификация и авторизация
- [x] CRUD для основных сущностей
- [x] Telegram Bot
- [ ] Web интерфейс (Next.js)
- [ ] Мобильное приложение
- [ ] Интеграции с платежными системами
- [ ] ML для прогнозирования
- [ ] Интеграция с 1С

## 🛡 Безопасность

- JWT токены для API
- Bcrypt для паролей
- Rate limiting
- CORS настройки
- SQL injection защита через ORM
- XSS защита в шаблонах

## 📝 Лицензия

Распространяется под лицензией MIT. См. `LICENSE` для подробностей.

## 👥 Команда

- **Вы** - Основатель и разработчик

## 🙏 Благодарности

- FastAPI community
- Aiogram developers
- Все contributors

## 📞 Контакты

- Email: your-email@example.com
- Telegram: @yourusername

---

<p align="center">Сделано с ❤️ для вендингового бизнеса</p>
>>>>>>> ee0500e (Initial VendHub setup)
