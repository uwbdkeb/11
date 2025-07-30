from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from bot.states.driver_states import ShiftState
from bot.keyboards.reply import get_main_menu, get_vehicle_condition_menu, get_cancel_menu
from bot.utils.database import Database
from bot.utils.validators import validate_mileage
from datetime import datetime

router = Router()
db = Database()

@router.message(lambda message: message.text == "🚀 Начать смену")
async def start_shift(message: types.Message, state: FSMContext):
    """Начало смены"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    # Проверка на активную смену
    active_shift = await db.get_active_shift(user_id)
    if active_shift:
        await message.answer(
            f"⚠️ У вас уже есть активная смена, начатая {active_shift['start_time']}\n"
            f"Завершите текущую смену перед началом новой.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "📸 Пожалуйста, сделайте фотографию автомобиля перед началом смены.\n"
        "Это необходимо для документирования состояния:",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(ShiftState.waiting_for_start_photo)

@router.message(StateFilter(ShiftState.waiting_for_start_photo))
async def process_start_photo(message: types.Message, state: FSMContext):
    """Обработка фотографии начала смены"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Начало смены отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию автомобиля:",
            reply_markup=get_cancel_menu()
        )
        return
    
    # Сохраняем фото
    photo_id = message.photo[-1].file_id
    await state.update_data(start_photo=photo_id)
    
    await message.answer(
        "🚗 Укажите текущий пробег автомобиля (в километрах):\n"
        "Например: 12345",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(ShiftState.waiting_for_mileage_start)

@router.message(StateFilter(ShiftState.waiting_for_mileage_start))
async def process_start_mileage(message: types.Message, state: FSMContext):
    """Обработка показаний пробега в начале смены"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Начало смены отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.text or not validate_mileage(message.text):
        await message.answer(
            "❌ Неверный формат пробега. Введите число в километрах:\n"
            "Например: 12345",
            reply_markup=get_cancel_menu()
        )
        return
    
    mileage_start = int(message.text.strip())
    
    # Получаем данные из состояния
    data = await state.get_data()
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    # Создаем новую смену
    shift_id = await db.create_shift(
        user_id=user_id,
        start_photo=data['start_photo'],
        mileage_start=mileage_start
    )
    
    await message.answer(
        f"✅ Смена №{shift_id} успешно начата!\n\n"
        f"🕐 Время начала: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n"
        f"🚗 Пробег: {mileage_start} км\n\n"
        f"Желаем удачной работы! 🚚",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "🏁 Завершить смену")
async def end_shift(message: types.Message, state: FSMContext):
    """Завершение смены"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    # Проверка на активную смену
    active_shift = await db.get_active_shift(user_id)
    if not active_shift:
        await message.answer(
            "❌ У вас нет активной смены для завершения.\n"
            "Начните смену для продолжения работы.",
            reply_markup=get_main_menu()
        )
        return
    
    await state.update_data(shift_id=active_shift['id'])
    
    await message.answer(
        "📸 Пожалуйста, сделайте фотографию автомобиля в конце смены:\n"
        "Это необходимо для документирования состояния:",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(ShiftState.waiting_for_end_photo)

@router.message(StateFilter(ShiftState.waiting_for_end_photo))
async def process_end_photo(message: types.Message, state: FSMContext):
    """Обработка фотографии окончания смены"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Завершение смены отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию автомобиля:",
            reply_markup=get_cancel_menu()
        )
        return
    
    # Сохраняем фото
    photo_id = message.photo[-1].file_id
    await state.update_data(end_photo=photo_id)
    
    await message.answer(
        "🚗 Укажите конечный пробег автомобиля (в километрах):\n"
        "Например: 12450",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(ShiftState.waiting_for_mileage_end)

@router.message(StateFilter(ShiftState.waiting_for_mileage_end))
async def process_end_mileage(message: types.Message, state: FSMContext):
    """Обработка показаний пробега в конце смены"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Завершение смены отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.text or not validate_mileage(message.text):
        await message.answer(
            "❌ Неверный формат пробега. Введите число в километрах:\n"
            "Например: 12450",
            reply_markup=get_cancel_menu()
        )
        return
    
    mileage_end = int(message.text.strip())
    data = await state.get_data()
    
    # Валидация конечного пробега
    shift_info = await db.get_shift_info(data['shift_id'])
    if shift_info and mileage_end <= shift_info['mileage_start']:
        await message.answer(
            f"❌ Конечный пробег ({mileage_end} км) не может быть меньше или равен начальному ({shift_info['mileage_start'] if shift_info else 0} км).\n"
            f"Введите корректное значение:",
            reply_markup=get_cancel_menu()
        )
        return
    
    await state.update_data(mileage_end=mileage_end)
    
    await message.answer(
        "🚗 Оцените состояние автомобиля после смены:",
        reply_markup=get_vehicle_condition_menu()
    )
    await state.set_state(ShiftState.waiting_for_vehicle_condition)

@router.message(StateFilter(ShiftState.waiting_for_vehicle_condition))
async def process_vehicle_condition(message: types.Message, state: FSMContext):
    """Обработка состояния автомобиля"""
    valid_conditions = ["✅ Отличное", "👍 Хорошее", "⚠️ Удовлетворительное", "❌ Требует ремонта"]
    
    if message.text == "🔙 Назад в меню":
        await message.answer("❌ Завершение смены отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if message.text not in valid_conditions:
        await message.answer(
            "❌ Пожалуйста, выберите состояние из предложенных вариантов:",
            reply_markup=get_vehicle_condition_menu()
        )
        return
    
    # Получаем все данные
    data = await state.get_data()
    condition_map = {
        "✅ Отличное": "excellent",
        "👍 Хорошее": "good", 
        "⚠️ Удовлетворительное": "satisfactory",
        "❌ Требует ремонта": "needs_repair"
    }
    
    vehicle_condition = condition_map[message.text]
    
    # Завершаем смену
    await db.end_shift(
        shift_id=data['shift_id'],
        end_photo=data['end_photo'],
        mileage_end=data['mileage_end'],
        vehicle_condition=vehicle_condition
    )
    
    # Расчет статистики
    distance = data['mileage_end'] - await db.get_shift_start_mileage(data['shift_id'])
    shift_info = await db.get_shift_info(data['shift_id'])
    if not shift_info:
        await message.answer("❌ Ошибка при получении информации о смене.", reply_markup=get_main_menu())
        await state.clear()
        return
    duration = datetime.now() - datetime.fromisoformat(shift_info['start_time'])
    
    await message.answer(
        f"✅ Смена №{data['shift_id']} успешно завершена!\n\n"
        f"📊 Статистика смены:\n"
        f"⏰ Продолжительность: {duration}\n"
        f"🛣️ Пройдено: {distance} км\n"
        f"🚗 Состояние ТС: {message.text}\n\n"
        f"Спасибо за работу! 👏",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "📊 Мои смены")
async def show_shifts_history(message: types.Message):
    """Показать историю смен водителя"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    shifts = await db.get_driver_shifts(user_id, limit=10)
    
    if not shifts:
        await message.answer(
            "📊 У вас пока нет завершенных смен.\n"
            "Начните первую смену для ведения статистики!",
            reply_markup=get_main_menu()
        )
        return
    
    shifts_text = "📊 **Ваши последние смены:**\n\n"
    
    for shift in shifts:
        status = "🟢 Активна" if shift['end_time'] is None else "🔴 Завершена"
        duration = "В процессе" if shift['end_time'] is None else str(
            datetime.fromisoformat(shift['end_time']) - datetime.fromisoformat(shift['start_time'])
        )
        distance = "—" if shift['mileage_end'] is None else f"{shift['mileage_end'] - shift['mileage_start']} км"
        
        shifts_text += (
            f"**Смена #{shift['id']}** {status}\n"
            f"📅 {datetime.fromisoformat(shift['start_time']).strftime('%d.%m.%Y %H:%M')}\n"
            f"⏰ Длительность: {duration}\n"
            f"🛣️ Пройдено: {distance}\n"
            f"──────────────\n"
        )
    
    await message.answer(shifts_text, parse_mode="Markdown", reply_markup=get_main_menu())
