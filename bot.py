from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardButton, InlineKeyboardMarkup,
    Message, CallbackQuery
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.types import FSInputFile

import logging
import asyncio
from functools import partial
import os
import requests

# 👇 импорт твоих функций
from encar_parser import parse_encar
from tamoz_parser import fill_rastamozhka_form

TOKEN = "7942224733:AAEZ3egHCgFcOBWc8Oq11A--nJ8DQkt2C3M"

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class CalcCarState(StatesGroup):
    waiting_for_url = State()
    confirming_age = State()
    calculating_final = State()


# --- Состояния FSM --- #
class CalcCarState(StatesGroup):
    waiting_for_url = State()

async def run_in_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))
 
# --- Клавиатура главного меню --- #
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="Рассчитать стоимость авто")],
        [KeyboardButton(text="Получить консультацию")],
        [KeyboardButton(text="О компании")],
        [KeyboardButton(text="Этапы покупки авто подробно")],  # Новая кнопка
        [KeyboardButton(text="Telegram-канал")],
        [KeyboardButton(text="WhatsApp")],
        [KeyboardButton(text="YouTube видео")],
    ])
    return keyboard

def get_usd_to_rub_rate() -> float:
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
        data = response.json()
        usd = data['Valute']['USD']['Value']
        return float(usd)
    except Exception as e:
        print(f"Ошибка получения курса USD: {e}")
        return 90.0  # запасной курс

# --- Получение курса KRW → RUB --- #
def get_krw_to_rub_rate() -> float:
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js")
        data = response.json()
        krw = data['Valute']['KRW']['Value']
        return float(krw)
    except Exception as e:
        print(f"Ошибка получения курса: {e}")
        return 0.07  # запасной курс

# --- Расчёт стоимости --- #
def calculate_final_price(
    age: str = None,
    engine: str = None,
    power: int = None,
    volume: int = None,
    price: int = None,
    curr: str = "KRW",
    max_retries: int = 3
) -> float:
    """Расчет итоговой стоимости с учетом типа авто"""
    krw_rate = get_krw_to_rub_rate()
    usd_rate = get_usd_to_rub_rate()
    price_won = price
    broker_fee = 90_000
    delivery_cost = 1000 * usd_rate

    # Электромобиль - упрощенный расчет
    if engine == "4":  # 4 - код электромобиля
        base_price = price_won * (krw_rate/1000)
        return round((base_price + delivery_cost) * 1.3 + delivery_cost + broker_fee + 200000, 2)

    # Обычный авто - полный расчет
    customs_str = fill_rastamozhka_form(
        age=age,
        engine=engine,
        power=power,
        volume=volume,
        price=float(price_won),
        curr=curr
    )
    customs_price = float(customs_str.replace(" ", "").replace(",", "."))

    return round(customs_price + delivery_cost + broker_fee + 200000, 2)





# --- Старт --- #
@router.message(CommandStart())
async def send_welcome(message: Message):
    welcome_text = """
    Приветствуем вас в YU Auto-Trade Co.Ltd!

    Мы рады видеть вас в нашем телеграм-боте, который создан для того, чтобы сделать процесс покупки автомобиля из Кореи максимально простым и удобным. Здесь вы сможете:

    🚗 Рассчитать стоимость автомобиля под ключ
    💬 Получить онлайн консультацию от наших экспертов
    📦 Узнать о всех этапах доставки и оформления

    Ваш новый автомобиль уже ждет вас!
    """

    photo = FSInputFile("welcome.jpg")  # 💥 ВАЖНО: используем FSInputFile для локального файла

    builder = InlineKeyboardBuilder()
    builder.button(text="Начать", callback_data="start_menu")

    await message.answer_photo(photo=photo, caption=welcome_text, reply_markup=builder.as_markup())


# --- Главное меню --- #
@router.callback_query(F.data == "start_menu")
async def show_main_menu(callback_query: CallbackQuery):
    await callback_query.message.answer("Главное меню:", reply_markup=get_main_menu())
    await callback_query.answer()


@router.message(F.text == "Этапы покупки авто подробно")
async def handle_steps(message: Message):
    await message.answer("📘 Ознакомьтесь со статьёй: https://dzen.ru/a/Zt2KmIZPxyrRwym5")

@router.callback_query(F.data == "calc_details")
async def show_calculation_details(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем сохраненные данные
        data = await state.get_data()
        car_data = data.get("original_data")
        last_price = data.get("last_price")

        if not car_data or not last_price:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return

        # Получаем курс валют (для отображения)
        usd_rate = get_usd_to_rub_rate()
        krw_rate = get_krw_to_rub_rate()
        delivery_vlad = 1000 * usd_rate
        delivery_moscow = 200000
        broker_fee = 90000

        # Рассчитываем таможенные платежи (из уже готовой цены)
        customs_payment = last_price - delivery_vlad - delivery_moscow - broker_fee - (int(car_data['Price (₩)'])*krw_rate/1000)

        await callback.message.answer(
            f"🧮 <b>Детализация расчета:</b>\n\n"
            f"🇰🇷 <b>Стоимость в Корее:</b> {car_data['Price (₩)']} ₩ / {str(int(car_data['Price (₩)'])*krw_rate/1000).replace(".",",")} ₽\n"
            f"🛃 <b>Таможенные платежи:</b> {customs_payment:,.2f} ₽\n"
            f"🚢 <b>Доставка до Владивостока:</b> 1000$ (~{delivery_vlad:,.0f} ₽)\n"
            f"👔 <b>Услуги брокера:</b> {broker_fee:,.0f} ₽\n"
            f"🚛 <b>Доставка до Москвы:</b> {delivery_moscow:,.0f} ₽\n\n"
            f"💵 <b>Итого:</b> {last_price:,.2f} ₽\n\n"
            f"ℹ️ Курс доллара: {usd_rate:.2f} ₽",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="ℹ️ Услуги брокера", callback_data="broker_details")],
                [InlineKeyboardButton(text="💬 Консультация", url="https://t.me/AutoTradeCoLtd")],
                [InlineKeyboardButton(text="🔄 Новый расчет", callback_data="start_menu")]
            ])
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Ошибка детализации: {str(e)}")
        await callback.answer("❌ Ошибка при отображении данных", show_alert=True)

@router.callback_query(F.data == "broker_details")
async def show_broker_services(callback: CallbackQuery):
    await callback.message.answer(
        "👔 <b>Услуги таможенного брокера (90.000₽):</b>\n\n"
        "• СБКТС\n• ЭПТС\n• Временная регистрация\n"
        "• СВХ\n• Выгрузка в порту\n• Лаборатория\n\n"
        "⚠️ <i>Возможна доплата 3000-5000₽ за СВХ при просрочке оплаты пошлины</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Консультация", url="https://t.me/AutoTradeCoLtd")],
            [InlineKeyboardButton(text="🔄 Новый расчет", callback_data="start_menu")]
        ])
    )
    await callback.answer()


# --- Обработка меню --- #
@router.message(F.text == "Рассчитать стоимость авто")
async def handle_calc_request(message: Message, state: FSMContext):
    await message.answer("Введите ссылку на автомобиль с сайта www.encar.com")
    await state.set_state(CalcCarState.waiting_for_url)

@router.message(F.text == "Получить консультацию")
async def handle_consult_request(message: Message):
    await message.answer("Свяжитесь с нашим менеджером: @AutoTradeCoLtd")

@router.message(F.text == "О компании")
async def handle_about(message: Message):
    await message.answer("""

YU Auto-Trade Co.Ltd – ваш надежный партнер в мире автомобилей из Кореи!

Мы обеспечиваем тщательный подбор авто учитывая все ваши пожелания, выбирая самые лучшие по состоянию и стоимости.

Мы не берем дополнительных оплат за нашу работу, скрытых комиссий и тп, у нас вы платите только за свой автомобиль и его доставку (доп. расходы, например комплект новой резины обсуждаются отдельно).

Нам доверяют клиенты из Росиии, Казахстана, ОАЭ и не только. Живые отзывы вы можете посмотреть в нашем тг-канале: https://t.me/YuAutotrade

Мы предоставляем полную информацию о каждом автомобиле, включая историю, технические характеристики, подробные видео-обзоры и фотографии посл осмотров. Вы всегда будете в курсе всех деталей по выбранным авто.

Мы сопровождаем вам на каждом этапе – от выбора автомобиля до его доставки.

По всем вопросам обращайтесь @AutoTradeCoLtd

Следите за нами в социальных сетях:
- Запрещенная соцсеть Instagram: https://www.instagram.com/yuautotrade?igsh=bWttdnUxYmVwOWNp
- VK: https://vk.com/yuautotrade
- YouTube: https://youtube.com/@autotradecoltd?si=EAFdBi02XZJ7sq_A
- Канал в Тelegram: https://t.me/YuAutotrade
- Яндекс Дзен: https://dzen.ru/a/Zt2KmIZPxyrRwym5

YU Auto-Trade Co.Ltd – ваш надежный партнёр
""")

@router.message(F.text == "Telegram-канал")
async def handle_telegram_link(message: Message):
    await message.answer("Подпишитесь на наш Telegram-канал: https://t.me/YuAutotrade")

@router.message(F.text == "WhatsApp")
async def handle_whatsapp(message: Message):
    await message.answer("Напишите нам в WhatsApp: https://wa.clck.bar/821055568394?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5!%20%D0%9C%D0%B5%D0%BD%D1%8F%20%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D0%B5%D1%81%D1%83%D0%B5%D1%82%20%D0%BF%D0%BE%D0%BA%D1%83%D0%BF%D0%BA%D0%B0%20%D0%B0%D0%B2%D1%82%D0%BE%D0%BC%D0%BE%D0%B1%D0%B8%D0%BB%D1%8F%20%D0%B8%D0%B7%20%D0%9A%D0%BE%D1%80%D0%B5%D0%B8")

@router.message(F.text == "YouTube видео")
async def handle_youtube(message: Message):
    await message.answer("Посмотрите наше видео: https://youtube.com/examplevideo")

@router.message(F.text.startswith("https://fem.encar.com/cars/"))
async def handle_encar_link(message: Message, state: FSMContext):
    url = message.text.strip()
    await message.answer("🔍 Парсим информацию об автомобиле...\nЭто может занять некоторое время")

    try:
        # Выносим синхронный парсинг в отдельный поток
        result = await run_in_thread(parse_encar, url)
        await message.answer("Я не сломался и не завис, я считаю таможенный платеж, еще немного и вы увидите стоимость машины")
        if not result or any(v == "Не найдено" for v in result.values()):
            await message.answer("🚫 Не удалось получить данные по ссылке. Попробуйте другую.")
            return
        
        
        # Сохраняем оригинальные данные
        await state.update_data(
            original_data=result,
            current_age=result["Age category"]
        )

        # Выносим синхронный расчет в отдельный поток
        if result["Engine type"] == "4":
            # Для электромобилей передаем только необходимые параметры
            final_price = await run_in_thread(
                calculate_final_price,
                engine="4",  # Главный маркер электромобиля
                price=float(result["Price (₩)"])
            )
        else:
            # Для обычных авто передаем все параметры
            final_price = await run_in_thread(
                calculate_final_price,
                age=result["Age category"],
                engine=result["Engine type"],
                power=150,  # Можно получать из данных или оставить по умолчанию
                volume=int(result["Engine volume"]),
                price=float(result["Price (₩)"])
            )

        # Сохраняем последнюю цену в состоянии
        await state.update_data(last_price=final_price)

        engine = None

        if result['Engine type'] == "1":
            engine = "Бензин"
        elif result['Engine type'] == "2":
            engine = "Дизель"
        elif result['Engine type'] == "3":
            engine ="Гибрид"
        elif result['Engine type'] == "4":
            engine = "Электро"

        # Остальной код обработки ответа остается без изменений
        await message.answer(
            f"<b>Стоимость автомобиля под ключ во Владивостоке: </b>\n\n"
            f"<b>{final_price:,.2f} ₽</b>\n\n"
            f"<b>Год и месяц выпуска: </b>{result['Manufacture date']}"
            f"<i>(у иностранных авто указана дата первичной постановки на учет, а не вин-код/дата производства, в среднем разница составляет 3-4 месяца)</i>\n"
            f"<b>Пробег:</b> {result['Mileage']}\n"
            f"<b>Возраст: </b> {result['Age category']}\n"
            f"<b>Тип двигателя:</b> {engine}\n"
            f"<b>Объём двигателя:</b> {result['Engine volume']}\n"
            f"ℹ️ <i>Стоимость может изменяться в зависимости от курса валют и индивидуальных параметров автомобиля. Для точного расчета напишите менеджеру</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Калькуляция стоимости авто", callback_data="calc_details")],
                [InlineKeyboardButton(text="Изменить возраст", callback_data="change_age")],
                [InlineKeyboardButton(text="Получить консультацию", url="https://t.me/AutoTradeCoLtd")]
            ])
        )

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")
        logging.error(f"Error in handle_encar_link: {str(e)}")

@router.callback_query(F.data == "change_age")
async def show_age_options(callback: CallbackQuery):
    """Показываем кнопки выбора возрастной категории"""
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="До 3 лет", callback_data="age_cat_0-3")],
            [InlineKeyboardButton(text="3–5 лет", callback_data="age_cat_3-5")],
            [InlineKeyboardButton(text="5–7 лет", callback_data="age_cat_5-7")],
            [InlineKeyboardButton(text="Старше 7 лет", callback_data="age_cat_7-0")],
        ])
    )
    await callback.answer("Выберите возрастную категорию")

@router.callback_query(F.data.startswith("age_cat_"))
async def process_age_change(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем выбранную возрастную категорию
        age_category = callback.data.split("_")[-1]  # "0-3", "3-5", "5-7", "7-0"

        # Достаем сохраненные данные
        user_data = await state.get_data()
        car_data = user_data.get("original_data")
        print(car_data)

        if not car_data:
            await callback.answer("❌ Данные не найдены. Начните расчет заново.", show_alert=True)
            return

        await callback.message.edit_text("🔄 Пересчитываем стоимость...")

        # Расчет стоимости
        if car_data["Engine type"] == "4":
            final_price = calculate_final_price(
                engine="4",
                price=float(car_data["Price (₩)"])
            )
        else:
            final_price = calculate_final_price(
                age=age_category,
                engine=car_data["Engine type"],
                power=150,
                volume=int(car_data["Engine volume"]),
                price=float(car_data["Price (₩)"])
            )

        # Сохраняем новую цену и возраст
        await state.update_data(
            last_price=final_price,
            current_age=age_category
        )

        # Форматируем вывод
        age_display = {
            "0-3": "до 3 лет",
            "3-5": "от 3 до 5 лет",
            "5-7": "от 5 до 7 лет",
            "7-0": "старше 7 лет"
        }.get(age_category, car_data['Age category'])

        await callback.message.edit_text(
            f"🚗 <b>Стоимость автомобиля под ключ в Москве:</b> {final_price:,.2f} ₽\n\n"
            f"📅 <b>Год выпуска:</b> {car_data['Manufacture date']}\n"
            f"<i>(дата первичной постановки на учет, разница с производством 3-4 месяца)</i>\n\n"
            f"🛠 <b>Объём двигателя:</b> {car_data['Engine volume']}\n"
            f"📊 <b>Возрастная категория:</b> {age_display}\n\n"
            f"ℹ️ Стоимость может изменяться. Для точного расчета напишите менеджеру",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧮 Калькуляция стоимости", callback_data="calc_details")],
                [InlineKeyboardButton(text="💬 Консультация", url="https://t.me/AutoTradeCoLtd")],
                [InlineKeyboardButton(text="🔄 Новый расчет", callback_data="start_menu")]
            ])
        )

    except Exception as e:
        logging.error(f"Ошибка в process_age_change: {str(e)}")
        await callback.message.edit_text(
            "❌ Ошибка при пересчете. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💼 Менеджер", url="https://t.me/AutoTradeCoLtd")]]
            )
        )


# --- Запуск бота --- #
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
