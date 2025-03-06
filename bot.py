from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import mysql.connector
import csv
import asyncio
import os

TOKEN = "8067818247:AAEr0596gnhNPbHyKaNgnzsGTrLmR31Lw00"
ADMIN_ID = 784590273  # Замените на реальный Telegram ID админа

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("HOST_MSQL"),
        user=os.getenv("USER_MSQL"),
        password=os.getenv("PASSWORD_MSQL"),
        database=os.getenv("DATABASE_MSQL")
    )
    return conn

async def fetch_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Products")
    products = cursor.fetchall()
    conn.close()
    return products

async def add_product(name, description, price, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Products (name, description, price, category_id) VALUES (%s, %s, %s, %s)", 
                   (name, description, price, category_id))
    conn.commit()
    conn.close()

async def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Products WHERE product_id = %s", (product_id,))
    conn.commit()
    conn.close()

async def export_products():
    products = await fetch_products()
    file_path = "products.csv"
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["ID", "Name", "Description", "Price", "Category ID"])
        writer.writerows(products)
    return file_path

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.button(text="Добавить продукт", callback_data="add_product")
        builder.button(text="Удалить продукт", callback_data="delete_product")
        builder.button(text="Выгрузить список", callback_data="export_products")
        builder.adjust(1)
        await message.answer("Админ-меню:", reply_markup=builder.as_markup())
    else:
        await message.answer("У вас нет доступа к этой команде.")

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа")
        return
    
    if callback.data == "add_product":
        await callback.message.answer("Отправьте данные продукта в формате: Имя, Описание, Цена, Категория ID")
    elif callback.data == "delete_product":
        await callback.message.answer("Отправьте ID продукта, который нужно удалить")
    elif callback.data == "export_products":
        file_path = await export_products()
        file = FSInputFile(file_path)
        await callback.message.answer_document(file)
    await callback.answer()

@dp.message()
async def process_message(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.split(", ")
    if len(text) == 4:
        try:
            name, description, price, category_id = text
            await add_product(name, description, float(price), int(category_id))
            await message.answer("Продукт добавлен!")
        except ValueError:
            await message.answer("Ошибка в формате данных.")
    elif text[0].isdigit():
        product_id = int(text[0])
        await delete_product(product_id)
        await message.answer("Продукт удалён!")
    else:
        await message.answer("Неверный формат ввода.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())