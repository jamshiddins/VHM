# setup-telegram-bot.ps1
# PowerShell скрипт для настройки Telegram бота VendHub

Write-Host "🤖 Настройка Telegram бота VendHub..." -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

# 1. Создание Python скрипта настройки бота
Write-Host "`n📄 Создание скрипта настройки бота..." -ForegroundColor Yellow

# Создание директории scripts если не существует
New-Item -ItemType Directory -Path "scripts" -Force | Out-Null

$botSetupScript = @'
# scripts/setup_telegram_bot.py
"""
Скрипт для настройки Telegram бота в production
"""
import asyncio
import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Начать работу"),
        BotCommand(command="menu", description="📋 Главное меню"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="operator", description="👷 Меню оператора"),
        BotCommand(command="warehouse", description="📦 Меню склада"),
        BotCommand(command="manager", description="👔 Меню менеджера"),
        BotCommand(command="admin", description="👨‍💼 Меню администратора"),
        BotCommand(command="cancel", description="❌ Отменить операцию"),
    ]
    
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("✅ Команды бота установлены")


async def setup_webhook(bot: Bot, webhook_url: str):
    """Настройка webhook для production"""
    # Удаление старого webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Установка нового webhook
    await bot.set_webhook(
        url=webhook_url,
        max_connections=100,
        drop_pending_updates=True
    )
    
    # Проверка webhook
    webhook_info = await bot.get_webhook_info()
    logger.info(f"✅ Webhook установлен: {webhook_info.url}")
    logger.info(f"   Pending updates: {webhook_info.pending_update_count}")
    

async def setup_bot_info(bot: Bot):
    """Обновление информации о боте"""
    # Установка описания
    await bot.set_my_description(
        description="🤖 VendHub Bot - система управления сетью вендинговых автоматов.\n\n"
                   "Функции:\n"
                   "• 📋 Управление задачами\n"
                   "• 📦 Учет товаров и склад\n"
                   "• 💰 Инкассация\n"
                   "• 📊 Отчеты и аналитика\n\n"
                   "Начните с команды /start"
    )
    
    # Установка краткого описания
    await bot.set_my_short_description(
        short_description="Система управления вендинговыми автоматами"
    )
    
    logger.info("✅ Информация о боте обновлена")


async def check_bot_health(bot: Bot):
    """Проверка здоровья бота"""
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот работает: @{me.username}")
        logger.info(f"   ID: {me.id}")
        logger.info(f"   Имя: {me.first_name}")
        
        # Проверка webhook
        webhook = await bot.get_webhook_info()
        if webhook.url:
            logger.info(f"✅ Webhook активен: {webhook.url}")
        else:
            logger.warning("⚠️  Webhook не настроен")
            
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка проверки бота: {e}")
        return False


async def main():
    """Основная функция настройки"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://api.vendhub.uz/webhook")
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        logger.info("🚀 Начинаем настройку Telegram бота...")
        
        # Проверка бота
        if not await check_bot_health(bot):
            return
        
        # Установка команд
        await setup_bot_commands(bot)
        
        # Обновление информации
        await setup_bot_info(bot)
        
        # Настройка webhook (только для production)
        if os.getenv("ENVIRONMENT") == "production":
            await setup_webhook(bot, WEBHOOK_URL)
        else:
            logger.info("ℹ️  Webhook не настраивается (не production)")
        
        logger.info("✅ Настройка бота завершена успешно!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка настройки: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
'@

$botSetupScript | Out-File -FilePath "scripts\setup_telegram_bot.py" -Encoding UTF8
Write-Host "  ✓ scripts/setup_telegram_bot.py создан" -ForegroundColor Gray

# 2. Создание PowerShell обертки для запуска
Write-Host "`n📄 Создание PowerShell скрипта запуска..." -ForegroundColor Yellow

$runBotSetup = @'
# scripts/run-bot-setup.ps1
# PowerShell скрипт для запуска настройки Telegram бота

Write-Host "🤖 Запуск настройки Telegram бота..." -ForegroundColor Green

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
    Write-Host "⚠️ BOT_TOKEN не найден в .env файле!" -ForegroundColor Yellow
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

Write-Host "`n✅ Готово!" -ForegroundColor Green
'@

$runBotSetup | Out-File -FilePath "scripts\run-bot-setup.ps1" -Encoding UTF8
Write-Host "  ✓ scripts/run-bot-setup.ps1 создан" -ForegroundColor Gray

# 3. Создание скрипта для получения информации о боте
Write-Host "`n📄 Создание скрипта проверки бота..." -ForegroundColor Yellow

$checkBotScript = @'
# scripts/check_bot_info.py
"""
Скрипт для получения информации о Telegram боте
"""
import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv
import json

load_dotenv()

async def get_bot_info():
    """Получение полной информации о боте"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Информация о боте
        me = await bot.get_me()
        print("🤖 ИНФОРМАЦИЯ О БОТЕ:")
        print(f"   ID: {me.id}")
        print(f"   Username: @{me.username}")
        print(f"   Имя: {me.first_name}")
        print(f"   Поддержка inline: {me.supports_inline_queries}")
        
        # Webhook
        webhook = await bot.get_webhook_info()
        print(f"\n🔗 WEBHOOK:")
        print(f"   URL: {webhook.url or 'Не установлен'}")
        print(f"   Pending updates: {webhook.pending_update_count}")
        
        # Команды
        commands = await bot.get_my_commands()
        print(f"\n📋 КОМАНДЫ ({len(commands)}):")
        for cmd in commands:
            print(f"   /{cmd.command} - {cmd.description}")
        
        # Ссылка для добавления в группу
        print(f"\n🔗 ССЫЛКИ:")
        print(f"   Прямая: https://t.me/{me.username}")
        print(f"   Добавить в группу: https://t.me/{me.username}?startgroup=true")
        print(f"   Админ панель: https://t.me/{me.username}?start=admin")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(get_bot_info())
'@

$checkBotScript | Out-File -FilePath "scripts\check_bot_info.py" -Encoding UTF8
Write-Host "  ✓ scripts/check_bot_info.py создан" -ForegroundColor Gray

# 4. Создание скрипта для настройки webhook
Write-Host "`n📄 Создание скрипта настройки webhook..." -ForegroundColor Yellow

$webhookScript = @'
# scripts/setup_webhook.py
"""
Скрипт для настройки webhook Telegram бота
"""
import asyncio
import os
import sys
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def setup_webhook(webhook_url: str = None):
    """Настройка webhook"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    if not webhook_url:
        webhook_url = os.getenv("WEBHOOK_URL", "https://api.vendhub.uz/webhook")
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Удаление старого webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print("🗑️ Старый webhook удален")
        
        # Установка нового
        await bot.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
        
        # Проверка
        info = await bot.get_webhook_info()
        print(f"📊 Статус: {info.url}")
        print(f"   Pending updates: {info.pending_update_count}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

async def remove_webhook():
    """Удаление webhook"""
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook удален")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "remove":
            asyncio.run(remove_webhook())
        else:
            asyncio.run(setup_webhook(sys.argv[1]))
    else:
        asyncio.run(setup_webhook())
'@

$webhookScript | Out-File -FilePath "scripts\setup_webhook.py" -Encoding UTF8
Write-Host "  ✓ scripts/setup_webhook.py создан" -ForegroundColor Gray

# 5. Создание .env.bot шаблона
Write-Host "`n📄 Создание шаблона .env.bot..." -ForegroundColor Yellow

$envBotTemplate = @'
# .env.bot - Настройки Telegram бота
# Скопируйте в .env и заполните значениями

# Telegram Bot
BOT_TOKEN=your-bot-token-from-botfather
BOT_ADMIN_IDS=123456789,987654321
BOT_WEBHOOK_URL=https://api.vendhub.uz/webhook
USE_WEBHOOK=False  # True для production

# Bot Settings
BOT_NAME=VendHub Bot
BOT_USERNAME=vendhub_bot
BOT_DESCRIPTION=Система управления вендинговыми автоматами

# Telegram API (опционально)
TELEGRAM_API_ID=your-api-id
TELEGRAM_API_HASH=your-api-hash

# Режим работы
ENVIRONMENT=development
DEBUG=True
'@

$envBotTemplate | Out-File -FilePath ".env.bot" -Encoding UTF8
Write-Host "  ✓ .env.bot создан" -ForegroundColor Gray

# 6. Создание инструкций
Write-Host "`n📝 Создание инструкций..." -ForegroundColor Yellow

$instructions = @"
# 📱 Инструкции по настройке Telegram бота VendHub

## 🚀 Быстрый старт

### 1. Создание бота в Telegram
1. Откройте [@BotFather](https://t.me/botfather)
2. Отправьте команду `/newbot`
3. Введите имя бота: `VendHub System`
4. Введите username: `vendhub_bot` (или ваш уникальный)
5. Сохраните полученный токен

### 2. Настройка .env файла
\`\`\`bash
# Скопируйте токен в .env файл
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
BOT_ADMIN_IDS=ваш_telegram_id
\`\`\`

### 3. Получение вашего Telegram ID
Отправьте любое сообщение боту [@userinfobot](https://t.me/userinfobot)

### 4. Запуск настройки бота
\`\`\`powershell
# В PowerShell
.\scripts\run-bot-setup.ps1

# Или напрямую Python
python scripts\setup_telegram_bot.py
\`\`\`

### 5. Проверка бота
\`\`\`powershell
python scripts\check_bot_info.py
\`\`\`

## 🔧 Дополнительные настройки

### Установка аватара бота
1. В BotFather: `/setuserpic`
2. Загрузите квадратное изображение (минимум 512x512)

### Настройка описания
1. `/setdescription` - полное описание
2. `/setabouttext` - краткое описание

### Настройка webhook (для production)
\`\`\`powershell
# Установить webhook
python scripts\setup_webhook.py https://api.yourdomain.com/webhook

# Удалить webhook (для локальной разработки)
python scripts\setup_webhook.py remove
\`\`\`

## 🛡️ Безопасность

1. **Никогда** не публикуйте BOT_TOKEN
2. Используйте webhook только через HTTPS
3. Ограничьте доступ к админ командам через BOT_ADMIN_IDS
4. Регулярно проверяйте активность бота

## 📊 Мониторинг

### Проверка статуса бота
\`\`\`powershell
# Информация о боте
python scripts\check_bot_info.py

# Проверка webhook
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
\`\`\`

### Логи бота
\`\`\`powershell
# В Docker
docker-compose logs -f telegram_bot

# Локально
tail -f logs/bot.log
\`\`\`

## 🚨 Решение проблем

### Бот не отвечает
1. Проверьте правильность токена
2. Проверьте подключение к интернету
3. Убедитесь, что бот запущен

### Webhook не работает
1. Проверьте SSL сертификат
2. Убедитесь, что URL доступен извне
3. Проверьте логи nginx

### Команды не работают
1. Перезапустите настройку команд
2. Проверьте права доступа в коде
3. Убедитесь, что пользователь в базе данных

## 📞 Полезные ссылки

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Aiogram Documentation](https://docs.aiogram.dev/)
- [@BotFather](https://t.me/botfather) - управление ботом
- [@userinfobot](https://t.me/userinfobot) - получить свой ID
"@

$instructions | Out-File -FilePath "TELEGRAM_BOT_SETUP.md" -Encoding UTF8
Write-Host "  ✓ TELEGRAM_BOT_SETUP.md создан" -ForegroundColor Gray

# Итоговый вывод
Write-Host "`n✅ Настройка Telegram бота завершена!" -ForegroundColor Green
Write-Host "`n📋 Созданные файлы:" -ForegroundColor Yellow
Write-Host "  ✓ scripts/setup_telegram_bot.py - основной скрипт настройки"
Write-Host "  ✓ scripts/run-bot-setup.ps1 - PowerShell обертка"
Write-Host "  ✓ scripts/check_bot_info.py - проверка информации о боте"
Write-Host "  ✓ scripts/setup_webhook.py - настройка webhook"
Write-Host "  ✓ .env.bot - шаблон переменных окружения"
Write-Host "  ✓ TELEGRAM_BOT_SETUP.md - подробные инструкции"

Write-Host "`n⚠️  Следующие шаги:" -ForegroundColor Yellow
Write-Host "1. Создайте бота через @BotFather"
Write-Host "2. Скопируйте BOT_TOKEN в файл .env"
Write-Host "3. Запустите: .\scripts\run-bot-setup.ps1"
Write-Host "4. Прочитайте TELEGRAM_BOT_SETUP.md для подробностей"

Write-Host "`n🤖 Команды для быстрого старта:" -ForegroundColor Cyan
Write-Host "  Настройка бота: python scripts\setup_telegram_bot.py"
Write-Host "  Проверка бота: python scripts\check_bot_info.py"
Write-Host "  Webhook setup: python scripts\setup_webhook.py"