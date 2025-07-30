from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states.driver_states import AdminState
from bot.keyboards.reply import get_main_menu, get_cancel_menu, get_admin_menu
from bot.keyboards.inline import get_vehicle_assignment_keyboard
from bot.utils.database import Database
from bot.utils.validators import validate_phone_number
from bot.config import Config

router = Router()
db = Database()
config = Config()

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Команда входа в административную панель"""
    if not message.from_user:
        await message.answer("❌ Ошибка: не удается определить пользователя.")
        return
    
    user_id = message.from_user.id
    
    # Отладочная информация
    await message.answer(f"🔍 Ваш ID: {user_id}\nПроверяю права администратора...")
    
    if not config.is_admin(user_id):
        await message.answer(
            f"❌ У вас нет прав администратора.\n"
            f"Ваш ID: {user_id}\n"
            f"Админские ID: {config.admin_ids}"
        )
        return
    
    await message.answer(
        "🔧 **Административная панель**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_menu()
    )

@router.message(lambda message: message.text == "👤 Добавить водителя")
async def add_driver_start(message: types.Message, state: FSMContext):
    """Начало процесса добавления водителя"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if not config.is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.", reply_markup=get_main_menu())
        return
    
    await message.answer(
        "👤 **Добавление нового водителя**\n\n"
        "Введите полное имя водителя:",
        parse_mode="Markdown",
        reply_markup=get_cancel_menu()
    )
    
    await state.set_state(AdminState.waiting_for_driver_name)

@router.message(StateFilter(AdminState.waiting_for_driver_name))
async def process_driver_name(message: types.Message, state: FSMContext):
    """Обработка имени водителя"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Добавление водителя отменено.", reply_markup=get_admin_menu())
        await state.clear()
        return
    
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(
            "❌ Пожалуйста, введите корректное имя (минимум 2 символа):",
            reply_markup=get_cancel_menu()
        )
        return
    
    driver_name = message.text.strip()
    await state.update_data(driver_name=driver_name)
    
    await message.answer(
        f"✅ Имя: {driver_name}\n\n"
        "📱 Теперь введите номер телефона водителя:\n"
        "Формат: +7XXXXXXXXXX или 8XXXXXXXXXX",
        reply_markup=get_cancel_menu()
    )
    
    await state.set_state(AdminState.waiting_for_driver_phone)

@router.message(StateFilter(AdminState.waiting_for_driver_phone))
async def process_driver_phone(message: types.Message, state: FSMContext):
    """Обработка номера телефона водителя"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Добавление водителя отменено.", reply_markup=get_admin_menu())
        await state.clear()
        return
    
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, введите номер телефона:",
            reply_markup=get_cancel_menu()
        )
        return
    
    phone = message.text.strip()
    normalized_phone = validate_phone_number(phone)
    
    if not normalized_phone:
        await message.answer(
            "❌ Неверный формат номера телефона.\n"
            "Используйте формат: +7XXXXXXXXXX или 8XXXXXXXXXX",
            reply_markup=get_cancel_menu()
        )
        return
    
    # Проверяем, не существует ли уже водитель с таким номером
    existing_driver = await db.get_driver_by_phone(normalized_phone)
    if existing_driver:
        await message.answer(
            f"❌ Водитель с номером {normalized_phone} уже существует:\n"
            f"👤 {existing_driver['name']}\n\n"
            "Введите другой номер телефона:",
            reply_markup=get_cancel_menu()
        )
        return
    
    await state.update_data(driver_phone=normalized_phone)
    
    # Получаем список доступных автомобилей
    available_vehicles = await db.get_available_vehicles()
    
    data = await state.get_data()
    
    if available_vehicles:
        keyboard = get_vehicle_assignment_keyboard(available_vehicles)
        await message.answer(
            f"✅ Телефон: {normalized_phone}\n\n"
            f"🚗 Выберите автомобиль для водителя **{data['driver_name']}**:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        await state.set_state(AdminState.waiting_for_vehicle_assignment)
    else:
        # Если нет доступных автомобилей, создаем водителя без назначенного ТС
        await create_driver_without_vehicle(message, state, data, normalized_phone)

async def create_driver_without_vehicle(message: types.Message, state: FSMContext, data: dict, phone: str):
    """Создание водителя без назначенного автомобиля"""
    try:
        driver_id = await db.create_driver(
            name=data['driver_name'],
            phone=phone,
            vehicle_id=None
        )
        
        await message.answer(
            f"✅ **Водитель успешно добавлен!**\n\n"
            f"👤 Имя: {data['driver_name']}\n"
            f"📱 Телефон: {phone}\n"
            f"🚗 Автомобиль: Не назначен\n"
            f"🆔 ID: {driver_id}\n\n"
            f"⚠️ Назначьте автомобиль водителю через меню управления автопарком.",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при создании водителя: {str(e)}",
            reply_markup=get_admin_menu()
        )
        await state.clear()

@router.callback_query(StateFilter(AdminState.waiting_for_vehicle_assignment))
async def process_vehicle_assignment(callback: types.CallbackQuery, state: FSMContext):
    """Обработка назначения автомобиля"""
    if not callback.data or not callback.data.startswith("assign_vehicle_"):
        await callback.answer("❌ Ошибка выбора автомобиля")
        return
    
    vehicle_id = int(callback.data.replace("assign_vehicle_", ""))
    data = await state.get_data()
    
    try:
        # Создаем водителя с назначенным автомобилем
        driver_id = await db.create_driver(
            name=data['driver_name'],
            phone=data['driver_phone'],
            vehicle_id=vehicle_id
        )
        
        # Получаем информацию об автомобиле
        vehicle_info = await db.get_vehicle_info(vehicle_id)
        
        if callback.message:
            await callback.message.edit_text(
                f"✅ **Водитель успешно добавлен!**\n\n"
                f"👤 Имя: {data['driver_name']}\n"
                f"📱 Телефон: {data['driver_phone']}\n"
                f"🚗 Автомобиль: {vehicle_info['model'] if vehicle_info else 'Ошибка'} ({vehicle_info['license_plate'] if vehicle_info else 'N/A'})\n"
                f"🆔 ID: {driver_id}",
                parse_mode="Markdown"
            )
            
            await callback.message.answer(
                "Водитель может теперь авторизоваться в боте, отправив команду /start",
                reply_markup=get_admin_menu()
            )
        
        await callback.answer("✅ Водитель добавлен")
        await state.clear()
        
    except Exception as e:
        if callback.message:
            await callback.message.edit_text(
                f"❌ Ошибка при создании водителя: {str(e)}"
            )
            await callback.message.answer(
                "Попробуйте снова",
                reply_markup=get_admin_menu()
            )
        await callback.answer("❌ Ошибка")
        await state.clear()

@router.message(lambda message: message.text == "🚗 Добавить автомобиль")
async def add_vehicle_start(message: types.Message, state: FSMContext):
    """Начало процесса добавления автомобиля"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if not config.is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.", reply_markup=get_main_menu())
        return
    
    await message.answer(
        "🚗 **Добавление нового автомобиля**\n\n"
        "Введите модель автомобиля:\n"
        "Например: Toyota Camry, Hyundai Solaris",
        parse_mode="Markdown",
        reply_markup=get_cancel_menu()
    )
    
    await state.set_state(AdminState.waiting_for_vehicle_model)

@router.message(StateFilter(AdminState.waiting_for_vehicle_model))
async def process_vehicle_model(message: types.Message, state: FSMContext):
    """Обработка модели автомобиля"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Добавление автомобиля отменено.", reply_markup=get_admin_menu())
        await state.clear()
        return
    
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(
            "❌ Пожалуйста, введите корректную модель автомобиля:",
            reply_markup=get_cancel_menu()
        )
        return
    
    vehicle_model = message.text.strip()
    await state.update_data(vehicle_model=vehicle_model)
    
    await message.answer(
        f"✅ Модель: {vehicle_model}\n\n"
        "🔢 Теперь введите государственный номер:\n"
        "Например: А123БВ77, В456ГД177",
        reply_markup=get_cancel_menu()
    )
    
    await state.set_state(AdminState.waiting_for_license_plate)

@router.message(StateFilter(AdminState.waiting_for_license_plate))
async def process_license_plate(message: types.Message, state: FSMContext):
    """Обработка государственного номера"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Добавление автомобиля отменено.", reply_markup=get_admin_menu())
        await state.clear()
        return
    
    if not message.text or len(message.text.strip()) < 6:
        await message.answer(
            "❌ Пожалуйста, введите корректный государственный номер:",
            reply_markup=get_cancel_menu()
        )
        return
    
    license_plate = message.text.strip().upper()
    
    # Проверяем, не существует ли уже автомобиль с таким номером
    existing_vehicle = await db.get_vehicle_by_license_plate(license_plate)
    if existing_vehicle:
        await message.answer(
            f"❌ Автомобиль с номером {license_plate} уже существует:\n"
            f"🚗 {existing_vehicle['model']}\n\n"
            "Введите другой номер:",
            reply_markup=get_cancel_menu()
        )
        return
    
    data = await state.get_data()
    
    try:
        vehicle_id = await db.create_vehicle(
            model=data['vehicle_model'],
            license_plate=license_plate
        )
        
        await message.answer(
            f"✅ **Автомобиль успешно добавлен!**\n\n"
            f"🚗 Модель: {data['vehicle_model']}\n"
            f"🔢 Номер: {license_plate}\n"
            f"🆔 ID: {vehicle_id}\n\n"
            f"Автомобиль готов к назначению водителю.",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при создании автомобиля: {str(e)}",
            reply_markup=get_admin_menu()
        )
        await state.clear()

@router.message(lambda message: message.text == "📋 Список водителей")
async def show_drivers_list(message: types.Message):
    """Показать список всех водителей"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if not config.is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.", reply_markup=get_main_menu())
        return
    
    drivers = await db.get_all_drivers()
    
    if not drivers:
        await message.answer(
            "📋 **Список водителей пуст**\n\n"
            "Добавьте первого водителя через '👤 Добавить водителя'",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
        return
    
    drivers_text = "📋 **Список всех водителей:**\n\n"
    
    for i, driver in enumerate(drivers, 1):
        status = "🟢 Активен" if driver['is_active'] else "🔴 Неактивен"
        vehicle_info = "Не назначен"
        
        if driver['vehicle_id']:
            vehicle = await db.get_vehicle_info(driver['vehicle_id'])
            if vehicle:
                vehicle_info = f"{vehicle['model']} ({vehicle['license_plate']})"
        
        drivers_text += (
            f"**{i}. {driver['name']}**\n"
            f"📱 {driver['phone']}\n"
            f"🚗 {vehicle_info}\n"
            f"📊 {status}\n"
            f"🆔 ID: {driver['id']}\n\n"
        )
    
    await message.answer(drivers_text, parse_mode="Markdown", reply_markup=get_admin_menu())

@router.message(lambda message: message.text == "🚗 Список автомобилей")
async def show_vehicles_list(message: types.Message):
    """Показать список всех автомобилей"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if not config.is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.", reply_markup=get_main_menu())
        return
    
    vehicles = await db.get_all_vehicles()
    
    if not vehicles:
        await message.answer(
            "🚗 **Автопарк пуст**\n\n"
            "Добавьте первый автомобиль через '🚗 Добавить автомобиль'",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
        return
    
    vehicles_text = "🚗 **Список всех автомобилей:**\n\n"
    
    for i, vehicle in enumerate(vehicles, 1):
        # Проверяем, назначен ли автомобиль водителю
        assigned_driver = await db.get_driver_by_vehicle_id(vehicle['id'])
        assignment_info = "Свободен"
        
        if assigned_driver:
            assignment_info = f"Назначен: {assigned_driver['name']}"
        
        condition_emoji = {
            'excellent': '✅',
            'good': '👍', 
            'satisfactory': '⚠️',
            'needs_repair': '🔧',
            'critical': '🚨'
        }.get(vehicle.get('condition', 'good'), '👍')
        
        vehicles_text += (
            f"**{i}. {vehicle['model']}**\n"
            f"🔢 {vehicle['license_plate']}\n"
            f"👤 {assignment_info}\n"
            f"{condition_emoji} Состояние: {vehicle.get('condition', 'Хорошее')}\n"
            f"⛽ Топливо: {vehicle.get('fuel_level', 100)}%\n"
            f"🆔 ID: {vehicle['id']}\n\n"
        )
    
    await message.answer(vehicles_text, parse_mode="Markdown", reply_markup=get_admin_menu())

@router.message(lambda message: message.text == "📊 Статистика системы")
async def show_system_statistics(message: types.Message):
    """Показать общую статистику системы"""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if not config.is_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.", reply_markup=get_main_menu())
        return
    
    # Получаем статистику
    stats = await db.get_system_statistics()
    
    stats_text = "📊 **Статистика системы**\n\n"
    
    stats_text += "👥 **Водители:**\n"
    stats_text += f"• Всего: {stats.get('total_drivers', 0)}\n"
    stats_text += f"• Активных: {stats.get('active_drivers', 0)}\n"
    stats_text += f"• На смене: {stats.get('drivers_on_shift', 0)}\n\n"
    
    stats_text += "🚗 **Автопарк:**\n"
    stats_text += f"• Всего ТС: {stats.get('total_vehicles', 0)}\n"
    stats_text += f"• Назначено: {stats.get('assigned_vehicles', 0)}\n"
    stats_text += f"• Свободных: {stats.get('available_vehicles', 0)}\n\n"
    
    stats_text += "📦 **Доставки:**\n"
    stats_text += f"• Сегодня: {stats.get('deliveries_today', 0)}\n"
    stats_text += f"• Завершено: {stats.get('completed_deliveries', 0)}\n"
    stats_text += f"• В процессе: {stats.get('active_deliveries', 0)}\n\n"
    
    stats_text += "🔧 **Отчеты:**\n"
    stats_text += f"• За сегодня: {stats.get('reports_today', 0)}\n"
    stats_text += f"• Проблемы: {stats.get('problem_reports', 0)}\n"
    
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=get_admin_menu())

@router.message(lambda message: message.text == "🔙 Выйти из админки")
async def exit_admin_panel(message: types.Message):
    """Выход из административной панели"""
    await message.answer(
        "👋 Вы вышли из административной панели.",
        reply_markup=get_main_menu()
    )