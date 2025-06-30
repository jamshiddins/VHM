# 📱 Инструкции по настройке Telegram бота VendHub

##  Быстрый старт

### 1. Создание бота в Telegram
1. Откройте [@BotFather](https://t.me/botfather)
2. Отправьте команду /newbot
3. Введите имя бота: VendHub System
4. Введите username: endhub_bot (или ваш уникальный)
5. Сохраните полученный токен

### 2. Настройка .env файла
\\\ash
# Скопируйте токен в .env файл
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
BOT_ADMIN_IDS=ваш_telegram_id
\\\

### 3. Получение вашего Telegram ID
Отправьте любое сообщение боту [@userinfobot](https://t.me/userinfobot)

### 4. Запуск настройки бота
\\\powershell
# В PowerShell
.\scripts\run-bot-setup.ps1

# Или напрямую Python
python scripts\setup_telegram_bot.py
\\\

### 5. Проверка бота
\\\powershell
python scripts\check_bot_info.py
\\\

##  Дополнительные настройки

### Установка аватара бота
1. В BotFather: /setuserpic
2. Загрузите квадратное изображение (минимум 512x512)

### Настройка описания
1. /setdescription - полное описание
2. /setabouttext - краткое описание

### Настройка webhook (для production)
\\\powershell
# Установить webhook
python scripts\setup_webhook.py https://api.yourdomain.com/webhook

# Удалить webhook (для локальной разработки)
python scripts\setup_webhook.py remove
\\\

## 🛡️ Безопасность

1. **Никогда** не публикуйте BOT_TOKEN
2. Используйте webhook только через HTTPS
3. Ограничьте доступ к админ командам через BOT_ADMIN_IDS
4. Регулярно проверяйте активность бота

##  Мониторинг

### Проверка статуса бота
\\\powershell
# Информация о боте
python scripts\check_bot_info.py

# Проверка webhook
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
\\\

### Логи бота
\\\powershell
# В Docker
docker-compose logs -f telegram_bot

# Локально
tail -f logs/bot.log
\\\

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
