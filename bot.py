import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# Загрузка токена (создайте .env с BOT_TOKEN=ваш_токен)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Инициализация бота
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- Состояния ---
class DriverStates(StatesGroup):
    waiting_for_phone = State()
    main_menu = State()

    # Водители
    drivers_list = State()
    select_car = State()
    start_shift = State()
    enter_mileage_start = State()
    upload_mileage_photo = State()
    upload_fuel_gas_photo = State()
    upload_oil_coolant_photo = State()
    upload_interior_photo = State()

    # Загрузка
    loading_list = State()
    loading_finished = State()

    # Доставка
    delivery_list = State()
    at_location = State()
    delivery_canceled = State()

    # Завершение смены
    end_shift_mileage = State()
    end_shift_photo = State()

    # Стоянка
    parking_mileage_photo = State()
    parking_fuel_gas_photo = State()
    parking_interior_photo = State()
    parking_general_photo = State()


# --- Главное меню ---
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Водители К"))
    builder.row(types.KeyboardButton(text="Загрузка К"))
    builder.row(types.KeyboardButton(text="Список доставки"))
    builder.row(types.KeyboardButton(text="Стоянка К"))
    return builder.as_markup(resize_keyboard=True)


# --- Старт ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("🚗 Добро пожаловать! Авторизация по номеру телефона.\nВведите ваш номер телефона:")
    await state.set_state(DriverStates.waiting_for_phone)


# --- Авторизация ---
@dp.message(DriverStates.waiting_for_phone)
async def phone_auth(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.isdigit() and '@' not in phone and '+' not in phone:
        await message.answer("Введите корректный номер телефона:")
        return
    await message.answer(f"✅ Авторизация успешна! Телефон: {phone}")
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


# --- Водители К ---
@dp.message(lambda msg: msg.text == "Водители К")
async def drivers_menu(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Список водителей - подтверждение"))
    builder.row(types.KeyboardButton(text="Выбор машины - подтверждение"))
    builder.row(types.KeyboardButton(text="Начало смены К"))
    builder.row(types.KeyboardButton(text="Назад"))
    await message.answer("📋 Меню водителей:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(DriverStates.drivers_list)


@dp.message(lambda msg: msg.text == "Список водителей - подтверждение")
async def confirm_drivers(message: types.Message):
    await message.answer("✅ Список водителей подтверждён.")


@dp.message(lambda msg: msg.text == "Выбор машины - подтверждение")
async def select_car_prompt(message: types.Message, state: FSMContext):
    await message.answer("🚘 Введите марку и номер машины:")
    await state.set_state(DriverStates.select_car)


@dp.message(DriverStates.select_car)
async def car_selected(message: types.Message, state: FSMContext):
    car = message.text
    await message.answer(f"✅ Машина {car} выбрана и подтверждена.")
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


@dp.message(lambda msg: msg.text == "Начало смены К")
async def start_shift(message: types.Message, state: FSMContext):
    await message.answer("🚗 Начало смены. Введите текущий пробег (в км):")
    await state.set_state(DriverStates.enter_mileage_start)


@dp.message(DriverStates.enter_mileage_start)
async def enter_mileage_start(message: types.Message, state: FSMContext):
    try:
        mileage = int(message.text)
        await state.update_data(mileage_start=mileage)
        await message.answer("📸 Сфотографируйте пробег (отправьте фото):")
        await state.set_state(DriverStates.upload_mileage_photo)
    except ValueError:
        await message.answer("🔢 Введите число!")


@dp.message(DriverStates.upload_mileage_photo, F.photo)
async def upload_mileage_photo(message: types.Message, state: FSMContext):
    await message.answer("✅ Фото пробега загружено.")
    await message.answer("⛽ Сфотографируйте уровень бензина/газа (2 фото):")
    await state.set_state(DriverStates.upload_fuel_gas_photo)


@dp.message(DriverStates.upload_fuel_gas_photo, F.photo)
async def upload_fuel_gas_photo(message: types.Message, state: FSMContext):
    await message.answer("✅ Фото бензина/газа загружено.")
    await message.answer("🛢️ Сфотографируйте уровень масла и антифриза:")
    await state.set_state(DriverStates.upload_oil_coolant_photo)


@dp.message(DriverStates.upload_oil_coolant_photo, F.photo)
async def upload_oil_coolant_photo(message: types.Message, state: FSMContext):
    await message.answer("✅ Фото масла и антифриза загружено.")
    await message.answer("🧼 Сфотографируйте салон автомобиля:")
    await state.set_state(DriverStates.upload_interior_photo)


@dp.message(DriverStates.upload_interior_photo, F.photo)
async def upload_interior_photo(message: types.Message, state: FSMContext):
    await message.answer("✅ Фото салона загружено.")
    await message.answer("✅ Начало смены завершено. Главное меню:", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


# --- Загрузка К ---
@dp.message(lambda msg: msg.text == "Загрузка К")
async def loading_menu(message: types.Message, state: FSMContext):
    orders = ["#1001 - Товар A", "#1002 - Товар B", "#1003 - Товар C"]
    builder = ReplyKeyboardBuilder()
    for order in orders:
        builder.row(types.KeyboardButton(text=f"{order} ✅"))
    builder.row(types.KeyboardButton(text="Загрузка окончена К"))
    builder.row(types.KeyboardButton(text="Назад"))
    await message.answer("📦 Отметьте загруженные товары:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(DriverStates.loading_list)


@dp.message(lambda msg: "✅" in msg.text and "#" in msg.text)
async def mark_loaded(message: types.Message):
    await message.answer(f"✔️ Загружено: {message.text.split(' ✅')[0]}")


@dp.message(lambda msg: msg.text == "Загрузка окончена К")
async def loading_finished(message: types.Message, state: FSMContext):
    await message.answer("✅ Загрузка завершена.")
    # Кнопки доставки
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="На месте К"),
        types.KeyboardButton(text="Отмена К")
    )
    builder.row(
        types.KeyboardButton(text="Подъем К"),
        types.KeyboardButton(text="Ожидание К")
    )
    builder.row(
        types.KeyboardButton(text="Оплата К")
    )
    builder.row(
        types.KeyboardButton(text="Навигация К"),
        types.KeyboardButton(text="Звонок К"),
        types.KeyboardButton(text="Вотсап К")
    )
    builder.row(types.KeyboardButton(text="Назад"))
    await message.answer("🚚 Доставка начата. Выберите действие:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(DriverStates.delivery_list)


# --- Список доставки ---
@dp.message(lambda msg: msg.text == "На месте К")
async def at_location(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Доставлено К"))
    builder.row(types.KeyboardButton(text="Назад"))
    await message.answer("📍 Вы на месте. Подтвердите доставку:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(DriverStates.at_location)


@dp.message(lambda msg: msg.text == "Доставлено К")
async def delivery_completed(message: types.Message, state: FSMContext):
    await message.answer("✅ Доставка завершена.")
    await message.answer("📦 Переход к следующему заказу или завершение смены.", reply_markup=get_main_keyboard())


@dp.message(lambda msg: msg.text == "Отмена К")
async def cancellation_menu(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Отказ в получении К"))
    builder.row(types.KeyboardButton(text="Перенос даты К"))
    builder.row(types.KeyboardButton(text="Назад"))
    await message.answer("❌ Причина отмены:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(DriverStates.delivery_canceled)


@dp.message(lambda msg: "Отказ" in msg.text or "Перенос" in msg.text)
async def cancellation_reason(message: types.Message, state: FSMContext):
    await message.answer(f"❌ Причина: {message.text}")
    await message.answer("📦 Продолжайте доставку.", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


# --- Завершить смену ---
@dp.message(lambda msg: msg.text == "Завершить смену К")
async def end_shift(message: types.Message, state: FSMContext):
    await message.answer("🏁 Введите конечный пробег (в км):")
    await state.set_state(DriverStates.end_shift_mileage)


@dp.message(DriverStates.end_shift_mileage)
async def end_shift_mileage(message: types.Message, state: FSMContext):
    try:
        mileage = int(message.text)
        await state.update_data(mileage_end=mileage)
        await message.answer("📸 Сфотографируйте конечный пробег:")
        await state.set_state(DriverStates.end_shift_photo)
    except ValueError:
        await message.answer("🔢 Введите число!")


@dp.message(DriverStates.end_shift_photo, F.photo)
async def end_shift_photo(message: types.Message, state: FSMContext):
    await message.answer("✅ Пробег и фото зафиксированы. Смена завершена.")
    await message.answer("🚗 Переход к стоянке:", reply_markup=get_parking_keyboard())
    await state.set_state(DriverStates.parking_mileage_photo)


# --- Стоянка К ---
def get_parking_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="Фото пробега"))
    builder.row(types.KeyboardButton(text="Фото бензин/газ"))
    builder.row(types.KeyboardButton(text="Фото салона"))
    builder.row(types.KeyboardButton(text="Общее фото автомобиля"))
    builder.row(types.KeyboardButton(text="Готово"))
    return builder.as_markup(resize_keyboard=True)


@dp.message(lambda msg: msg.text == "Стоянка К")
async def parking_menu(message: types.Message, state: FSMContext):
    await message.answer("📸 Стоянка: загрузите фото автомобиля.", reply_markup=get_parking_keyboard())
    await state.set_state(DriverStates.parking_mileage_photo)


@dp.message(lambda msg: msg.text == "Фото пробега")
async def parking_mileage(message: types.Message):
    await message.answer("📷 Сфотографируйте пробег:")


@dp.message(lambda msg: msg.text == "Фото бензин/газ")
async def parking_fuel_gas(message: types.Message):
    await message.answer("⛽ Сфотографируйте бензин/газ:")


@dp.message(lambda msg: msg.text == "Фото салона")
async def parking_interior(message: types.Message):
    await message.answer("🛋️ Сфотографируйте салон:")


@dp.message(lambda msg: msg.text == "Общее фото автомобиля")
async def parking_general(message: types.Message):
    await message.answer("📸 Сфотографируйте автомобиль снаружи:")


@dp.message(lambda msg: msg.text == "Готово")
async def parking_done(message: types.Message, state: FSMContext):
    await message.answer("✅ Все фото стоянки загружены. До встречи в следующей смене!")
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


# --- Назад ---
@dp.message(lambda msg: msg.text == "Назад")
async def go_back(message: types.Message, state: FSMContext):
    await message.answer("🔙 Возвращаемся в главное меню.", reply_markup=get_main_keyboard())
    await state.set_state(DriverStates.main_menu)


# --- Запуск бота ---
if __name__ == "__main__":
    print("🚀 Бот запущен...")
    dp.run_polling(bot)
