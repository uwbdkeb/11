from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from bot.states.driver_states import DeliveryState
from bot.keyboards.reply import get_main_menu, get_delivery_status_menu, get_cancel_menu, get_confirmation_menu
from bot.utils.database import Database
from datetime import datetime

router = Router()
db = Database()

@router.message(lambda message: message.text == "🚚 Доставка")
async def delivery_menu(message: types.Message):
    """Меню доставки"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    # Проверка активной смены
    active_shift = await db.get_active_shift(user_id)
    if not active_shift:
        await message.answer(
            "❌ Для работы с доставками необходимо начать смену.\n"
            "Нажмите '🚀 Начать смену' для продолжения.",
            reply_markup=get_main_menu()
        )
        return
    
    # Получаем активные доставки
    active_deliveries = await db.get_active_deliveries(user_id)
    pending_deliveries = await db.get_pending_deliveries(user_id)
    
    menu_text = "🚚 **Управление доставками**\n\n"
    
    if active_deliveries:
        menu_text += f"🔥 Активные доставки: {len(active_deliveries)}\n"
        for delivery in active_deliveries[:3]:  # Показываем только первые 3
            menu_text += f"• #{delivery['id']} - {delivery['address'][:30]}...\n"
    
    if pending_deliveries:
        menu_text += f"\n⏳ Ожидающие доставки: {len(pending_deliveries)}\n"
        for delivery in pending_deliveries[:3]:  # Показываем только первые 3
            menu_text += f"• #{delivery['id']} - {delivery['address'][:30]}...\n"
    
    if not active_deliveries and not pending_deliveries:
        menu_text += "📭 У вас нет назначенных доставок.\n"
    
    menu_text += "\n🎯 Выберите действие:"
    
    # Создаем динамическую клавиатуру
    keyboard = []
    
    if pending_deliveries:
        keyboard.append([types.KeyboardButton(text="🚀 Начать доставку")])
    
    if active_deliveries:
        keyboard.append([types.KeyboardButton(text="📍 Обновить статус")])
        keyboard.append([types.KeyboardButton(text="📸 Фото доставки")])
    
    keyboard.extend([
        [types.KeyboardButton(text="📋 Список доставок"), types.KeyboardButton(text="📊 История доставок")],
        [types.KeyboardButton(text="🔙 Главное меню")]
    ])
    
    reply_markup = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await message.answer(menu_text, parse_mode="Markdown", reply_markup=reply_markup)

@router.message(lambda message: message.text == "🚀 Начать доставку")
async def start_delivery(message: types.Message, state: FSMContext):
    """Начать доставку"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    pending_deliveries = await db.get_pending_deliveries(user_id)
    if not pending_deliveries:
        await message.answer(
            "❌ У вас нет ожидающих доставок.",
            reply_markup=get_main_menu()
        )
        return
    
    # Показываем список доставок для выбора
    deliveries_text = "📋 **Выберите доставку для начала:**\n\n"
    
    for i, delivery in enumerate(pending_deliveries, 1):
        deliveries_text += (
            f"{i}. **Заказ #{delivery['id']}**\n"
            f"📍 {delivery['address']}\n"
            f"📦 {delivery.get('description', 'Без описания')}\n"
            f"💰 {delivery.get('amount', 'Не указано')}\n"
            f"──────────────\n"
        )
    
    deliveries_text += "\nОтправьте номер доставки (например: 1) или отмените операцию:"
    
    await state.update_data(pending_deliveries=pending_deliveries)
    await message.answer(deliveries_text, parse_mode="Markdown", reply_markup=get_cancel_menu())
    await state.set_state(DeliveryState.waiting_for_address_confirmation)

@router.message(StateFilter(DeliveryState.waiting_for_address_confirmation))
async def confirm_delivery_address(message: types.Message, state: FSMContext):
    """Подтверждение адреса доставки"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Начало доставки отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    try:
        if not message.text:
            raise ValueError("Empty text")
        delivery_index = int(message.text.strip()) - 1
        data = await state.get_data()
        pending_deliveries = data['pending_deliveries']
        
        if delivery_index < 0 or delivery_index >= len(pending_deliveries):
            raise ValueError("Invalid index")
            
        selected_delivery = pending_deliveries[delivery_index]
        
    except (ValueError, IndexError):
        pending_count = len(await db.get_pending_deliveries(message.from_user.id)) if message.from_user else 0
        await message.answer(
            "❌ Неверный номер доставки. Введите число от 1 до "
            f"{pending_count}:",
            reply_markup=get_cancel_menu()
        )
        return
    
    await state.update_data(selected_delivery=selected_delivery)
    
    confirmation_text = (
        f"📋 **Подтвердите начало доставки:**\n\n"
        f"🆔 Заказ: #{selected_delivery['id']}\n"
        f"📍 Адрес: {selected_delivery['address']}\n"
        f"📦 Товары: {selected_delivery.get('description', 'Без описания')}\n"
        f"💰 Сумма: {selected_delivery.get('amount', 'Не указано')}\n"
        f"📞 Клиент: {selected_delivery.get('customer_phone', 'Не указан')}\n\n"
        f"Все данные корректны?"
    )
    
    await message.answer(confirmation_text, parse_mode="Markdown", reply_markup=get_confirmation_menu())

@router.message(lambda message: message.text in ["✅ Подтвердить", "❌ Отменить"] and message.reply_markup)
async def process_delivery_confirmation(message: types.Message, state: FSMContext):
    """Обработка подтверждения доставки"""
    if message.text == "❌ Отменить":
        await message.answer("❌ Начало доставки отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    data = await state.get_data()
    delivery = data['selected_delivery']
    
    # Обновляем статус доставки на "в пути"
    if message.from_user:
        await db.start_delivery(delivery['id'], message.from_user.id)
    
    await message.answer(
        "📸 Сделайте фотографию отправления (автомобиль с товаром):\n"
        "Это подтвердит начало доставки.",
        reply_markup=get_cancel_menu()
    )
    await state.set_state(DeliveryState.waiting_for_departure_photo)

@router.message(StateFilter(DeliveryState.waiting_for_departure_photo))
async def process_departure_photo(message: types.Message, state: FSMContext):
    """Обработка фото отправления"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Доставка отменена.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию:",
            reply_markup=get_cancel_menu()
        )
        return
    
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    delivery = data['selected_delivery']
    
    # Сохраняем фото отправления
    await db.save_delivery_photo(delivery['id'], photo_id, 'departure')
    
    await message.answer(
        f"✅ Доставка #{delivery['id']} начата!\n\n"
        f"📍 Адрес: {delivery['address']}\n"
        f"📞 Телефон клиента: {delivery.get('customer_phone', 'Не указан')}\n\n"
        f"🚚 Доставляйте товар и не забудьте сделать фото при передаче клиенту!",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "📍 Обновить статус")
async def update_delivery_status(message: types.Message, state: FSMContext):
    """Обновление статуса доставки"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    active_deliveries = await db.get_active_deliveries(user_id)
    
    if not active_deliveries:
        await message.answer(
            "❌ У вас нет активных доставок.",
            reply_markup=get_main_menu()
        )
        return
    
    # Если одна доставка - сразу переходим к статусу
    if len(active_deliveries) == 1:
        delivery = active_deliveries[0]
        await state.update_data(selected_delivery=delivery)
        await message.answer(
            f"📋 **Доставка #{delivery['id']}**\n"
            f"📍 {delivery['address']}\n\n"
            f"Выберите статус доставки:",
            parse_mode="Markdown",
            reply_markup=get_delivery_status_menu()
        )
        await state.set_state(DeliveryState.waiting_for_delivery_status)
        return
    
    # Если несколько доставок - выбираем
    deliveries_text = "📋 **Выберите доставку для обновления:**\n\n"
    
    for i, delivery in enumerate(active_deliveries, 1):
        deliveries_text += (
            f"{i}. **#{delivery['id']}** - {delivery['address'][:40]}\n"
            f"   Статус: {delivery['status']}\n"
        )
    
    deliveries_text += "\nОтправьте номер доставки:"
    
    await state.update_data(active_deliveries=active_deliveries)
    await message.answer(deliveries_text, parse_mode="Markdown", reply_markup=get_cancel_menu())

@router.message(StateFilter(DeliveryState.waiting_for_delivery_status))
async def process_delivery_status(message: types.Message, state: FSMContext):
    """Обработка статуса доставки"""
    status_map = {
        "✅ Доставлено": "delivered",
        "❌ Не доставлено": "failed",
        "🔄 Перенос доставки": "rescheduled", 
        "🚫 Отмена заказа": "cancelled"
    }
    
    if message.text == "🔙 Назад в меню":
        await message.answer("Операция отменена.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if message.text not in status_map:
        await message.answer(
            "❌ Пожалуйста, выберите статус из предложенных:",
            reply_markup=get_delivery_status_menu()
        )
        return
    
    data = await state.get_data()
    delivery = data['selected_delivery']
    new_status = status_map[message.text]
    
    await state.update_data(new_status=new_status)
    
    if new_status == "delivered":
        await message.answer(
            "📸 Пожалуйста, сделайте фото подтверждения доставки:\n"
            "Это может быть фото переданного товара или подпись клиента.",
            reply_markup=get_cancel_menu()
        )
        await state.set_state(DeliveryState.waiting_for_delivery_photo)
    elif new_status in ["failed", "rescheduled", "cancelled"]:
        await message.answer(
            "📝 Укажите причину или комментарий:",
            reply_markup=get_cancel_menu()
        )
        await state.set_state(DeliveryState.waiting_for_return_reason)
    else:
        # Обновляем статус без дополнительных данных
        await db.update_delivery_status(delivery['id'], new_status)
        await message.answer(
            f"✅ Статус доставки #{delivery['id']} обновлен: {message.text}",
            reply_markup=get_main_menu()
        )
        await state.clear()

@router.message(StateFilter(DeliveryState.waiting_for_delivery_photo))
async def process_delivery_photo(message: types.Message, state: FSMContext):
    """Обработка фото доставки"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Обновление статуса отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте фотографию подтверждения:",
            reply_markup=get_cancel_menu()
        )
        return
    
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    delivery = data['selected_delivery']
    
    # Сохраняем фото и обновляем статус
    await db.save_delivery_photo(delivery['id'], photo_id, 'delivery')
    await db.update_delivery_status(delivery['id'], data['new_status'])
    
    await message.answer(
        f"✅ Доставка #{delivery['id']} успешно завершена!\n"
        f"📸 Фото подтверждения сохранено.\n\n"
        f"Отличная работа! 👏",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(StateFilter(DeliveryState.waiting_for_return_reason))
async def process_return_reason(message: types.Message, state: FSMContext):
    """Обработка причины возврата/переноса"""
    if message.text == "🚫 Отменить операцию":
        await message.answer("❌ Обновление статуса отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, укажите причину:",
            reply_markup=get_cancel_menu()
        )
        return
    
    reason = message.text.strip()
    if len(reason) < 5:
        await message.answer(
            "❌ Пожалуйста, укажите подробную причину (минимум 5 символов):",
            reply_markup=get_cancel_menu()
        )
        return
    
    data = await state.get_data()
    delivery = data['selected_delivery']
    
    # Обновляем статус с причиной
    await db.update_delivery_status(delivery['id'], data['new_status'], reason)
    
    status_text = {
        "failed": "❌ Не доставлено",
        "rescheduled": "🔄 Перенесено",
        "cancelled": "🚫 Отменено"
    }
    
    await message.answer(
        f"✅ Статус доставки #{delivery['id']} обновлен: {status_text[data['new_status']]}\n"
        f"📝 Причина: {reason}",
        reply_markup=get_main_menu()
    )
    
    await state.clear()

@router.message(lambda message: message.text == "📋 Список доставок")
async def show_deliveries_list(message: types.Message):
    """Показать список всех доставок"""
    if not message.from_user:
        return
    user_id = message.from_user.id
    
    if not await db.is_driver_authorized(user_id):
        await message.answer("❌ Необходимо пройти авторизацию. Отправьте /start")
        return
    
    all_deliveries = await db.get_all_driver_deliveries(user_id)
    
    if not all_deliveries:
        await message.answer(
            "📭 У вас пока нет назначенных доставок.",
            reply_markup=get_main_menu()
        )
        return
    
    # Группируем по статусам
    pending = [d for d in all_deliveries if d['status'] == 'pending']
    active = [d for d in all_deliveries if d['status'] == 'in_progress']  
    completed = [d for d in all_deliveries if d['status'] == 'delivered']
    failed = [d for d in all_deliveries if d['status'] in ['failed', 'cancelled', 'rescheduled']]
    
    list_text = "📋 **Все ваши доставки:**\n\n"
    
    if pending:
        list_text += f"⏳ **Ожидающие ({len(pending)}):**\n"
        for d in pending[:5]:
            list_text += f"• #{d['id']} - {d['address'][:30]}...\n"
        if len(pending) > 5:
            list_text += f"... и еще {len(pending) - 5}\n"
        list_text += "\n"
    
    if active:
        list_text += f"🔥 **Активные ({len(active)}):**\n"
        for d in active:
            list_text += f"• #{d['id']} - {d['address'][:30]}...\n"
        list_text += "\n"
    
    if completed:
        list_text += f"✅ **Завершенные ({len(completed)}):**\n"
        for d in completed[:3]:
            list_text += f"• #{d['id']} - {d['address'][:30]}...\n"
        if len(completed) > 3:
            list_text += f"... и еще {len(completed) - 3}\n"
        list_text += "\n"
    
    if failed:
        list_text += f"❌ **Проблемные ({len(failed)}):**\n"
        for d in failed[:3]:
            list_text += f"• #{d['id']} - {d['address'][:30]}...\n"
        if len(failed) > 3:
            list_text += f"... и еще {len(failed) - 3}\n"
    
    await message.answer(list_text, parse_mode="Markdown", reply_markup=get_main_menu())
