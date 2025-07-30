from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states.driver_states import AuthState
from bot.keyboards.reply import get_phone_request_menu, get_main_menu
from bot.utils.database import Database
from bot.utils.validators import validate_phone_number
import re

router = Router()
db = Database()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start - начало работы с ботом"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    # Проверяем, авторизован ли пользователь
    if await db.is_driver_authorized(user_id):
        driver_info = await db.get_driver_info(user_id)
        if driver_info:
            await message.answer(
                f"👋 Добро пожаловать обратно, {driver_info['name']}!\n"
                f"🚗 Ваш автомобиль: {driver_info.get('vehicle', 'Не назначен')}\n\n"
                f"Выберите действие:",
                reply_markup=get_main_menu()
            )
        else:
            await message.answer(
                "🚚 Добро пожаловать в систему управления доставкой!\n\n"
                "Для работы с ботом необходимо пройти авторизацию.\n"
                "Пожалуйста, отправьте ваш номер телефона:",
                reply_markup=get_phone_request_menu()
            )
            await state.set_state(AuthState.waiting_for_phone)
    else:
        await message.answer(
            "🚚 Добро пожаловать в систему управления доставкой!\n\n"
            "Для работы с ботом необходимо пройти авторизацию.\n"
            "Пожалуйста, отправьте ваш номер телефона:",
            reply_markup=get_phone_request_menu()
        )
        await state.set_state(AuthState.waiting_for_phone)

@router.message(StateFilter(AuthState.waiting_for_phone))
async def process_phone_auth(message: types.Message, state: FSMContext):
    """Обработка авторизации по номеру телефона"""
    phone_number = None
    
    # Получение номера телефона из контакта или текста
    if message.contact:
        phone_number = message.contact.phone_number
    elif message.text:
        phone_number = message.text.strip()
    
    if not phone_number:
        await message.answer(
            "❌ Пожалуйста, отправьте ваш номер телефона или используйте кнопку ниже:",
            reply_markup=get_phone_request_menu()
        )
        return
    
    # Валидация номера телефона
    normalized_phone = validate_phone_number(phone_number)
    if not normalized_phone:
        await message.answer(
            "❌ Неверный формат номера телефона.\n"
            "Пожалуйста, отправьте номер в формате +7XXXXXXXXXX:",
            reply_markup=get_phone_request_menu()
        )
        return
    
    # Проверка наличия водителя в базе данных
    driver_info = await db.get_driver_by_phone(normalized_phone)
    if not driver_info:
        await message.answer(
            "❌ Водитель с таким номером телефона не найден в системе.\n"
            "Обратитесь к администратору для регистрации."
        )
        await state.clear()
        return
    
    # Авторизация водителя
    if message.from_user:
        await db.authorize_driver(message.from_user.id, driver_info['id'])
    
    await message.answer(
        f"✅ Авторизация успешна!\n\n"
        f"👤 Имя: {driver_info['name']}\n"
        f"📱 Телефон: {normalized_phone}\n"
        f"🚗 Автомобиль: {driver_info.get('vehicle', 'Не назначен')}\n\n"
        f"Теперь вы можете управлять сменами и доставками:",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(Command("logout"))
async def cmd_logout(message: types.Message, state: FSMContext):
    """Команда выхода из системы"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if await db.is_driver_authorized(user_id):
        await db.logout_driver(user_id)
        await message.answer(
            "👋 Вы успешно вышли из системы.\n"
            "Для повторной авторизации отправьте команду /start",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer("❌ Вы не авторизованы в системе.")
    
    await state.clear()

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда помощи"""
    help_text = """
🚚 **Система управления доставкой** 

**Основные команды:**
• /start - Начать работу с ботом
• /help - Показать это сообщение
• /logout - Выйти из системы

**Функции бота:**
🚀 **Смены** - Начать/завершить рабочую смену
📦 **Загрузка** - Документирование загрузки товаров
🚚 **Доставка** - Отслеживание процесса доставки
🚗 **Автомобиль** - Контроль состояния транспорта
📊 **Отчеты** - Просмотр истории смен

**Требования:**
• Обязательная фотофиксация всех процессов
• Указание пробега в начале и конце смены
• Документирование состояния автомобиля

Для получения помощи обратитесь к администратору.
"""
    await message.answer(help_text, parse_mode="Markdown")
