import os
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import pytz
from flask import Flask
import logging

# === Настройки ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Требуется TELEGRAM_TOKEN")

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# === Логирование ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        "Привет! Я — бот с расписанием 📚\n"
        "Выбери действие в меню👇",
        reply_markup=reply_markup
    )

# === Расписание по дням ===
async def day_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().replace("📅 ", "")
    day_map = {
        "понедельник": "понедельник", "вторник": "вторник", "среда": "среда",
        "четверг": "четверг", "пятница": "пятница", "суббота": "суббота",
        "воскресенье": "воскресенье",
        "сегодня": "сегодня"
    }
    weekday_map = {
        'monday': 'понедельник', 'tuesday': 'вторник', 'wednesday': 'среда',
        'thursday': 'четверг', 'friday': 'пятница', 'saturday': 'суббота', 'sunday': 'воскресенье'
    }
    
    target_day = day_map.get(text)
    if target_day == "сегодня":
        target_day = weekday_map.get(datetime.now(MOSCOW_TZ).strftime('%A').lower())

    if target_day:
        await update.message.reply_text(get_schedule(target_day), reply_markup=reply_markup)

# === Добавить пару ===
async def add_lesson_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите: День Время Предмет Кабинет\n"
        "Пример: понедельник 09:00 Математика Ауд. 205"
    )
    context.user_data['awaiting_lesson'] = True

async def handle_lesson_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_lesson'):
        try:
            parts = update.message.text.split(" ", 3)
            if len(parts) < 4:
                await update.message.reply_text("❌ Неверный формат.")
                return

            day, time, subject, classroom = [p.strip() for p in parts]
            day = day.lower()

            conn = sqlite3.connect('schedule.db')
            c = conn.cursor()
            c.execute("INSERT INTO lessons (day, time, subject, classroom) VALUES (?, ?, ?, ?)",
                      (day, time, subject, classroom))
            conn.commit()
            conn.close()

            await update.message.reply_text(f"✅ Добавлено: {day} в {time} — {subject}")
            context.user_data['awaiting_lesson'] = False
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# === Напоминания ===
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        now = datetime.now(MOSCOW_TZ)
        target_time = (now + timedelta(minutes=15)).strftime('%H:%M')
        target_day = now.strftime('%A').lower()
        day_map = {
            'monday': 'понедельник', 'tuesday': 'вторник', 'wednesday': 'среда',
            'thursday': 'четверг', 'friday': 'пятница', 'saturday': 'суббота', 'sunday': 'воскресенье'
        }
        ru_day = day_map.get(target_day, 'понедельник')

        conn = sqlite3.connect('schedule.db')
        c = conn.cursor()
        c.execute("SELECT subject, classroom FROM lessons WHERE day=? AND time=?", (ru_day, target_time))
        rows = c.fetchall()
        conn.close()

        for subject, classroom in rows:
            if ADMIN_USER_ID:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"🔔 Через 15 минут: {subject} в {classroom}"
                )
    except Exception as e:
        logger.error(f"Ошибка в send_reminders: {e}")

# === Веб-сервер для keep-alive ===
app_flask = Flask(__name__)

@app_flask.route('/')
def index():
    return "Бот работает! 🚀"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app_flask.run(host="0.0.0.0", port=port)

# === Инициализация Job Queue ===
async def post_init(application: ApplicationBuilder) -> None:
    application.job_queue.run_repeating(send_reminders, interval=60, first=10)

# === Запуск ===
if __name__ == "__main__":
    init_db()

    from threading import Thread
    Thread(target=run_flask, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(➕ Добавить пару)$"), add_lesson_prompt))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(📅 (Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье|Сегодня))$"), day_schedule))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lesson_input))

    app.run_polling()