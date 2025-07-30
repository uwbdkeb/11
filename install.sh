#!/bin/bash

echo "🚀 Установка Telegram Driver Management Bot"
echo "=========================================="

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✅ Python найден"

# Создание виртуального окружения
echo "📦 Создание виртуального окружения..."
python3 -m venv venv

# Активация виртуального окружения
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Установка зависимостей
echo "�� Установка зависимостей..."
pip install -r requirements.txt

# Создание .env файла
if [ ! -f .env ]; then
    echo "📝 Создание .env файла..."
    cp .env.example .env
    echo "⚠️  Не забудьте добавить токен бота в файл .env"
else
    echo "✅ .env файл уже существует"
fi

echo ""
echo "🎉 Установка завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Отредактируйте файл .env и добавьте токен бота"
echo "2. Активируйте виртуальное окружение: source venv/bin/activate"
echo "3. Запустите бота: python bot.py"
echo ""
