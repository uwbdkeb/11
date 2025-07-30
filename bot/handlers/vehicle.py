from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from bot.states.driver_states import VehicleState
from bot.keyboards.reply import get_main_menu, get_cancel_menu
from bot.utils.database import Database
from bot.utils.validators import validate_fuel_level
from datetime import datetime

router = Router()
db = Database()

@router.message(lambda message: message.text == "🚗 Состояние автомобиля")
async def vehicle_menu(message: types.Message):
    """Меню управления состоянием автомобиля"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    driver_info = await db.get_driver_info(user_id)
    vehicle_info = await db.get_vehicle_info(driver_info['vehicle_id']) if driver_info and driver_info.get('vehicle_id') else None
    
    menu_text = "🚗 **Управление автомобилем**\n\n"
    
    if vehicle_info:
        menu_text += (
            f"🚙 **Ваш автомобиль:**\n"
            f"• Модель: {vehicle_info['model']}\n"
            f"• Номер: {vehicle_info['license_plate']}\n"
            f"• Пробег: {vehicle_info.get('current_mileage', 'Не указан')} км\n"
            f"• Состояние: {vehicle_info.get('condition', 'Не проверено')}\n\n"
        )
        
        # Получаем последние записи
        recent_reports = await db.get_recent_vehicle_reports(vehicle_info['id'], limit=3)
        if recent_reports:
            menu_text += "📋 **Последние отчеты:**\n"
            for report in recent_reports:
                report_date = datetime.fromisoformat(report['created_at']).strftime('%d.%m %H:%M')
                menu_text += f"• {report_date} - {report['report_type']}: {report['status']}\n"
    else:
        menu_text += "❌ Автомобиль не назначен. Обратитесь к администратору.\n"
    
    menu_text += "\n🎯 Выберите действие:"
    
    # Создаем клавиатуру
    keyboard = [
        [types.KeyboardButton(text="📸 Фото на стоянке"), types.KeyboardButton(text="⛽ Уровень топлива")],
        [types.KeyboardButton(text="🔧 Сообщить о поломке"), types.KeyboardButton(text="📋 История отчетов")],
        [types.KeyboardButton(text="🚗 Проверка перед выездом"), types.KeyboardButton(text="📊 Статистика ТС")],
        [types.KeyboardButton(text="🔙 Главное меню")]
    ]
    
    reply_markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await message.answer(menu_text, parse_mode="Markdown", reply_markup=reply_markup)

@router.message(lambda message: message.text == "📸 Фото на стоянке")
async def parking_photo_start(message: types.Message, state: FSMContext):
    """Начать процесс фотографирования на стоянке"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль. Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "📸 Сделайте фотографию автомобиля на стоянке.\n\n"
        "Фото должно четко показывать:\n"
        "• Общее состояние автомобиля\n"
        "• Номерной знак\n"
        "• Отсутствие повреждений\n\n"
        "Это поможет документировать состояние ТС:",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(VehicleState.waiting_for_parking_photo)

@router.message(StateFilter(VehicleState.waiting_for_parking_photo))
async def process_parking_photo(message: types.Message, state: FSMContext):
    """Обработка фото на стоянке"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Создание отчета отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию автомобиля:",
            reply_markup=get_cancel_menu()
        )
        return
    
    photo_id = message.photo[-1].file_id
    if not message.from_user:
        return
    user_id = message.from_user.id
    driver_info = await db.get_driver_info(user_id)
    
    if not driver_info:
        await message.answer("❌ Ошибка получения информации водителя.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Сохраняем отчет о парковке
    await db.create_vehicle_report(
        vehicle_id=driver_info['vehicle_id'],
        driver_id=driver_info['id'],
        report_type='parking',
        photo_id=photo_id,
        status='documented'
    )
    
    await message.answer(
        "✅ Фото автомобиля на стоянке сохранено!\n\n"
        "📸 Отчет создан и добавлен в историю.\n"
        "Спасибо за поддержание дисциплины! 👏",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "⛽ Уровень топлива")
async def fuel_level_start(message: types.Message, state: FSMContext):
    """Начать процесс указания уровня топлива"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль. Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "⛽ Укажите текущий уровень топлива в процентах.\n\n"
        "Примеры:\n"
        "• 85 (для 85%)\n"
        "• 50 (для половины бака)\n"
        "• 15 (для критически низкого уровня)\n\n"
        "Введите число от 0 до 100:",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(VehicleState.waiting_for_fuel_level)

@router.message(StateFilter(VehicleState.waiting_for_fuel_level))
async def process_fuel_level(message: types.Message, state: FSMContext):
    """Обработка уровня топлива"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Отчет о топливе отменен.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.text or not validate_fuel_level(message.text):
        await message.answer(
            "❌ Неверный формат. Введите число от 0 до 100:\n"
            "Например: 75",
            reply_markup=get_cancel_menu()
        )
        return
    
    fuel_level = int(message.text.strip())
    if not message.from_user:
        return
    user_id = message.from_user.id
    driver_info = await db.get_driver_info(user_id)
    
    if not driver_info:
        await message.answer("❌ Ошибка получения информации водителя.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Определяем статус по уровню топлива
    if fuel_level >= 75:
        status = "excellent"
        status_text = "✅ Отлично"
    elif fuel_level >= 50:
        status = "good"  
        status_text = "👍 Хорошо"
    elif fuel_level >= 25:
        status = "low"
        status_text = "⚠️ Низкий уровень"
    else:
        status = "critical"
        status_text = "🚨 Критический уровень"
    
    # Сохраняем отчет о топливе
    await db.create_vehicle_report(
        vehicle_id=driver_info['vehicle_id'],
        driver_id=driver_info['id'],
        report_type='fuel',
        status=status,
        notes=f"Уровень топлива: {fuel_level}%"
    )
    
    # Обновляем информацию об автомобиле
    if driver_info['vehicle_id']:
        await db.update_vehicle_fuel(driver_info['vehicle_id'], fuel_level)
    
    response_text = (
        f"⛽ Уровень топлива зафиксирован: {fuel_level}%\n"
        f"📊 Статус: {status_text}\n\n"
    )
    
    if fuel_level < 25:
        response_text += "🚨 **Внимание!** Низкий уровень топлива.\nРекомендуется заправка в ближайшее время.\n\n"
    elif fuel_level < 50:
        response_text += "⚠️ Рекомендуется следить за расходом топлива.\n\n"
    
    response_text += "✅ Отчет сохранен в системе."
    
    await message.answer(response_text, parse_mode="Markdown", reply_markup=get_main_menu())
    await state.clear()

@router.message(lambda message: message.text == "🔧 Сообщить о поломке")
async def damage_report_start(message: types.Message, state: FSMContext):
    """Начать процесс сообщения о поломке"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль. Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        return
    
    await message.answer(
        "🔧 **Сообщение о проблеме с автомобилем**\n\n"
        "Опишите подробно обнаруженную проблему:\n"
        "• Что именно не работает?\n"
        "• Когда это началось?\n"
        "• Влияет ли на безопасность?\n"
        "• Можно ли продолжать работу?\n\n"
        "Введите подробное описание:",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(VehicleState.waiting_for_damage_report)

@router.message(StateFilter(VehicleState.waiting_for_damage_report))
async def process_damage_report(message: types.Message, state: FSMContext):
    """Обработка сообщения о поломке"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Сообщение о поломке отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, опишите проблему:",
            reply_markup=get_cancel_menu()
        )
        return
    
    damage_description = message.text.strip()
    if len(damage_description) < 10:
        await message.answer(
            "❌ Пожалуйста, опишите проблему более подробно (минимум 10 символов):",
            reply_markup=get_cancel_menu()
        )
        return
    
    if not message.from_user:
        return
    user_id = message.from_user.id
    driver_info = await db.get_driver_info(user_id)
    
    if not driver_info:
        await message.answer("❌ Ошибка получения информации водителя.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Сохраняем отчет о поломке
    report_id = await db.create_vehicle_report(
        vehicle_id=driver_info['vehicle_id'],
        driver_id=driver_info['id'],
        report_type='damage',
        status='needs_repair',
        notes=damage_description
    )
    
    # Уведомляем администраторов (если нужно)
    # await notify_admins_about_damage(driver_info, damage_description)
    
    await message.answer(
        f"🔧 **Сообщение о поломке отправлено!**\n\n"
        f"📋 Номер отчета: #{report_id}\n"
        f"📝 Описание: {damage_description[:100]}...\n\n"
        f"🚨 **Важно!** Если проблема влияет на безопасность - "
        f"немедленно прекратите работу и свяжитесь с диспетчером.\n\n"
        f"✅ Ваш отчет передан в службу технического обслуживания.",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "🚗 Проверка перед выездом")
async def pre_trip_inspection(message: types.Message):
    """Проверка автомобиля перед выездом"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль. Обратитесь к администратору.",
            reply_markup=get_main_menu()
        )
        return
    
    # Получаем информацию об автомобиле
    vehicle_info = await db.get_vehicle_info(driver_info['vehicle_id'])
    if not vehicle_info:
        await message.answer(
            "❌ Ошибка получения информации об автомобиле.",
            reply_markup=get_main_menu()
        )
        return
    recent_reports = await db.get_recent_vehicle_reports(vehicle_info['id'], limit=5)
    
    inspection_text = "🚗 **Проверка перед выездом**\n\n"
    
    # Основная информация
    inspection_text += (
        f"🚙 **Автомобиль:** {vehicle_info['model']}\n"
        f"🔢 **Номер:** {vehicle_info['license_plate']}\n"
        f"📊 **Пробег:** {vehicle_info.get('current_mileage', 'Не указан')} км\n\n"
    )
    
    # Чек-лист проверки
    inspection_text += "📋 **Обязательная проверка:**\n"
    checklist = [
        "✅ Уровень топлива достаточен",
        "✅ Давление в шинах в норме", 
        "✅ Работают фары и габариты",
        "✅ Исправны тормоза",
        "✅ Чистые зеркала и стекла",
        "✅ Документы в автомобиле",
        "✅ Аптечка и огнетушитель на месте",
        "✅ Отсутствуют видимые повреждения"
    ]
    
    for item in checklist:
        inspection_text += f"• {item}\n"
    
    # Последние отчеты
    if recent_reports:
        inspection_text += "\n📋 **Последние отчеты:**\n"
        for report in recent_reports[:3]:
            report_date = datetime.fromisoformat(report['created_at']).strftime('%d.%m %H:%M')
            status_emoji = {"excellent": "✅", "good": "👍", "needs_repair": "🔧", "critical": "🚨"}.get(report['status'], "📝")
            inspection_text += f"• {status_emoji} {report_date} - {report['report_type']}\n"
    
    inspection_text += (
        f"\n⚠️ **Внимание!**\n"
        f"Перед началом работы убедитесь, что все пункты проверки выполнены.\n"
        f"При обнаружении проблем используйте '🔧 Сообщить о поломке'."
    )
    
    # Создаем клавиатуру с быстрыми действиями
    keyboard = [
        [types.KeyboardButton(text="✅ Все проверено, готов к работе")],
        [types.KeyboardButton(text="⛽ Проверить топливо"), types.KeyboardButton(text="🔧 Есть проблема")],
        [types.KeyboardButton(text="🔙 Назад")]
    ]
    
    reply_markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await message.answer(inspection_text, parse_mode="Markdown", reply_markup=reply_markup)

@router.message(lambda message: message.text == "✅ Все проверено, готов к работе")
async def confirm_pre_trip_inspection(message: types.Message):
    """Подтверждение готовности к работе"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    driver_info = await db.get_driver_info(user_id)
    
    if not driver_info:
        await message.answer("❌ Ошибка получения информации водителя.", reply_markup=get_main_menu())
        return
    
    # Создаем отчет о предрейсовой проверке
    await db.create_vehicle_report(
        vehicle_id=driver_info['vehicle_id'],
        driver_id=driver_info['id'],
        report_type='pre_trip_inspection',
        status='excellent',
        notes='Предрейсовая проверка пройдена успешно'
    )
    
    await message.answer(
        "✅ **Предрейсовая проверка завершена!**\n\n"
        "🚗 Автомобиль готов к работе\n"
        "📋 Отчет о проверке сохранен\n\n"
        "Желаем безопасной дороги! 🛣️",
        reply_markup=get_main_menu()
    )

@router.message(lambda message: message.text == "📋 История отчетов")
async def show_vehicle_reports_history(message: types.Message):
    """Показать историю отчетов по автомобилю"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль.",
            reply_markup=get_main_menu()
        )
        return
    
    reports = await db.get_recent_vehicle_reports(driver_info['vehicle_id'], limit=15)
    
    if not reports:
        await message.answer(
            "📋 История отчетов пуста.\n"
            "Создайте первый отчет о состоянии автомобиля!",
            reply_markup=get_main_menu()
        )
        return
    
    history_text = "📋 **История отчетов по автомобилю:**\n\n"
    
    # Группируем по типам
    report_types = {}
    for report in reports:
        report_type = report['report_type']
        if report_type not in report_types:
            report_types[report_type] = []
        report_types[report_type].append(report)
    
    type_names = {
        'parking': '🅿️ Фото на стоянке',
        'fuel': '⛽ Уровень топлива',
        'damage': '🔧 Поломки',
        'pre_trip_inspection': '🚗 Предрейсовые проверки',
        'maintenance': '🔧 Обслуживание'
    }
    
    for report_type, type_reports in report_types.items():
        type_name = type_names.get(report_type, report_type.title())
        history_text += f"**{type_name} ({len(type_reports)}):**\n"
        
        for report in type_reports[:5]:  # Показываем последние 5
            date = datetime.fromisoformat(report['created_at']).strftime('%d.%m %H:%M')
            status_emoji = {
                "excellent": "✅", 
                "good": "👍", 
                "satisfactory": "⚠️",
                "needs_repair": "🔧", 
                "critical": "🚨",
                "documented": "📸"
            }.get(report['status'], "📝")
            
            history_text += f"• {status_emoji} {date}"
            if report.get('notes'):
                notes_preview = report['notes'][:30] + "..." if len(report['notes']) > 30 else report['notes']
                history_text += f" - {notes_preview}"
            history_text += "\n"
        
        if len(type_reports) > 5:
            history_text += f"... и еще {len(type_reports) - 5}\n"
        history_text += "\n"
    
    await message.answer(history_text, parse_mode="Markdown", reply_markup=get_main_menu())

@router.message(lambda message: message.text == "📊 Статистика ТС")
async def show_vehicle_statistics(message: types.Message):
    """Показать статистику по автомобилю"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    driver_info = await db.get_driver_info(user_id)
    if not driver_info or not driver_info.get('vehicle_id'):
        await message.answer(
            "❌ У вас не назначен автомобиль.",
            reply_markup=get_main_menu()
        )
        return
    
    # Получаем статистику
    vehicle_stats = await db.get_vehicle_statistics(driver_info['vehicle_id'])
    vehicle_info = await db.get_vehicle_info(driver_info['vehicle_id'])
    
    if not vehicle_info:
        await message.answer(
            "❌ Ошибка получения информации об автомобиле.",
            reply_markup=get_main_menu()
        )
        return
    
    stats_text = f"📊 **Статистика автомобиля {vehicle_info['license_plate']}**\n\n"
    
    # Основные показатели
    stats_text += "🚗 **Основные показатели:**\n"
    stats_text += f"• Модель: {vehicle_info['model']}\n"
    stats_text += f"• Текущий пробег: {vehicle_info.get('current_mileage', 'Не указан')} км\n"
    stats_text += f"• Уровень топлива: {vehicle_info.get('fuel_level', 'Не указан')}%\n"
    stats_text += f"• Общее состояние: {vehicle_info.get('condition', 'Не проверено')}\n\n"
    
    # Статистика отчетов
    if vehicle_stats:
        stats_text += "📋 **Активность:**\n"
        stats_text += f"• Всего отчетов: {vehicle_stats.get('total_reports', 0)}\n"
        stats_text += f"• Отчетов о парковке: {vehicle_stats.get('parking_reports', 0)}\n"
        stats_text += f"• Проверок топлива: {vehicle_stats.get('fuel_reports', 0)}\n"
        stats_text += f"• Сообщений о поломках: {vehicle_stats.get('damage_reports', 0)}\n"
        stats_text += f"• Предрейсовых проверок: {vehicle_stats.get('inspection_reports', 0)}\n\n"
    
    # Последние события
    recent_events = await db.get_recent_vehicle_events(driver_info['vehicle_id'], limit=5)
    if recent_events:
        stats_text += "📅 **Последние события:**\n"
        for event in recent_events:
            if event.get('created_at'):
                event_date = datetime.fromisoformat(event['created_at']).strftime('%d.%m %H:%M')
                event_type = event.get('event_type')
                event_emoji = {
                    'shift_start': '🚀',
                    'shift_end': '🏁', 
                    'delivery_start': '📦',
                    'delivery_end': '✅',
                    'report_created': '📋'
                }.get(event_type if event_type else '', '📝')
                
                description = event.get('description', 'Событие без описания')
                stats_text += f"• {event_emoji} {event_date} - {description}\n"
    
    await message.answer(stats_text, parse_mode="Markdown", reply_markup=get_main_menu())
