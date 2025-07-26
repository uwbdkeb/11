# main.py
import os
import sqlite3
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
from flask import Flask

# === Настройки ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("Требуется TELEGRAM_TOKEN в переменных окружения")

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
if not ADMIN_USER_ID:
    raise ValueError("Требуется ADMIN_USER_ID в переменных окружения")

try:
    ADMIN_USER_ID = int(ADMIN_USER_ID)
except ValueError:
    raise ValueError("ADMIN_USER_ID должен быть числом")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

# === Настройка логирования ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
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

# === Инициализация базы данных ===
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
    # Пример данных
    try:
        c.execute("SELECT COUNT(*) FROM lessons")
        if c.fetchone()[0] == 0:
            examples = [
                ('понедельник', '09:00', 'Математика', 'Ауд. 205'),
                ('вторник', '12:00', 'Программирование', 'Комп. класс'),
            ]
            c.executemany("INSERT INTO lessons (day, time, subject, classroom) VALUES (?, ?, ?, ?)", examples)
            conn.commit()
            logger.info("База данных инициализирована с примерами")
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
    finally:
        conn.close()

# === Получение расписания ===
def get_schedule(day: str):
    try:
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
    except Exception as e:
        logger.error(f"Ошибка при получении расписания: {e}")
        return "❌ Ошибка при загрузке расписания."

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запустил бота")
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
        "сегодня": datetime.now(MOSCOW_TZ).strftime('%A').lower()
    }
    weekday_map = {
        'monday': 'понедельник', 'tuesday': 'вторник', 'wednesday': 'среда',
        'thursday': 'четверг', 'friday': 'пятница', 'saturday': 'суббота', 'sunday': 'воскресенье'
    }
    target_day = day_map.get(text)
    if target_day == "сегодня":
        target_day = weekday_map.get(datetime.now(MOSCOW_TZ).strftime('%A').lower())

    if target_day:
        logger.info(f"Пользователь запросил расписание на {target_day}")
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
                await update.message.reply_text("❌ Неверный формат. Пример: понедельник 09:00 Математика Ауд. 205")
                return

            day, time, subject, classroom = [p.strip() for p in parts]
            day = day.lower()

            conn = sqlite3.connect('schedule.db')
            c = conn.cursor()
            c.execute("INSERT INTO lessons (day, time, subject, classroom) VALUES (?, ?, ?, ?)",
                      (day, time, subject, classroom))
            conn.commit()
            conn.close()

            logger.info(f"Добавлена пара: {day} {time} — {subject}")
            await update.message.reply_text(f"✅ Добавлено: {day} в {time} — {subject}")
            context.user_data['awaiting_lesson'] = False
        except Exception as e:
            logger.error(f"Ошибка при добавлении пары: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# === Напоминания за 15 минут ===
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
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"🔔 Напоминание!\nЧерез 15 минут: *{subject}* в _{classroom}_",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Ошибка в напоминаниях: {e}")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"🚨 Ошибка в напоминаниях: {e}"
            )
        except:
            pass

# === Обработчик ошибок (отправка в Telegram) ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        logger.error(f"Произошла ошибка: {context.error}")
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"🚨 *Критическая ошибка в боте*\n\n```{context.error}```",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Не удалось отправить ошибку в Telegram: {e}")

# === Веб-сервер для keep-alive ===
app_flask = Flask(__name__)
@app_flask.route('/')
def index():
    return "Бот работает! 🚀"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app_flask.run(host="0.0.0.0", port=port)

# === Запуск бота ===
if __name__ == "__main__":
    init_db()

    # Запускаем веб-сервер в отдельном потоке
    from threading import Thread
    Thread(target=run_flask, daemon=True).start()

    # Напоминания каждую минуту
    scheduler.add_job(send_reminders, 'interval', minutes=1)
    scheduler.start()

    # Создаём приложение
    app = ApplicationBuilder().token(TOKEN).build()

    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)

    # Хэндлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(➕ Добавить пару)$"), add_lesson_prompt))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(📅 (Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье|Сегодня))$"), day_schedule))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lesson_input))

    logger.info("✅ Бот запущен и готов к работе!")
    app.run_polling()