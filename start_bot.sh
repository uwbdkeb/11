#!/bin/bash

# Активация виртуального окружения
source venv/bin/activate

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе .env.example"
    echo "Скопируйте .env.example в .env и добавьте токен вашего бота:"
    echo "cp .env.example .env"
    exit 1
fi

# Запуск бота
echo "🚀 Запуск Telegram бота..."
python bot.py
