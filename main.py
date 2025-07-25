import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
from flask import Flask

# === Настройки ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Требуется TELEGRAM_TOKEN")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

# === Клавиатура ===
keyboard = [
    [KeyboardButton("📅 Расписание")],
    [KeyboardButton("➕ Добавить пару")],
    [KeyboardButton("📅 Понедельник"), KeyboardButton("📅 Вторник")],
    [KeyboardButton("📅 Сегодня")]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Инициализация БД ===
def init_db():
    conn = sqlite3.connect('schedule.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY,
        day TEXT,
        time TEXT,
        subject TEXT,
        classroom TEXT
    )''')
    if c.execute("SELECT COUNT(*) FROM lessons").fetchone()[0] == 0:
        examples = [
            ('понедельник', '09:00', 'Математика', 'Ауд. 205'),
            ('вторник', '12:00', 'Программирование', 'Комп. класс'),
        ]
        c.executemany("INSERT INTO lessons VALUES (NULL, ?, ?, ?, ?)", examples)
    conn.commit()
    conn.close()

# === Получение расписания ===
def get_schedule(day: str):
    conn = sqlite3.connect('schedule.db')
    c = conn.cursor()
    c.execute("SELECT time, subject, classroom FROM lessons WHERE day=? ORDER BY time", (day,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return f"В {day} пар нет 🎉"
    
    result = f"📚 Расписание на {day.title()}:\n\n"
    for time, subject, classroom in rows:
        result += f"⏰ {time} — {subject}\n📍 {classroom}\n\n"
    return result

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет")