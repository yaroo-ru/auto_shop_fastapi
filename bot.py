from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import mysql.connector
import csv
import asyncio
import os
import json

TOKEN = "8067818247:AAEr0596gnhNPbHyKaNgnzsGTrLmR31Lw00"
ADMIN_ID = (784590273, 5680097082, 8129598483)  # Замените на реальный Telegram ID админа

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

# Функция для получения всех заказов
async def fetch_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Orders")
    orders = cursor.fetchall()
    conn.close()
    return orders

# Функция для получения заказов по user_id
async def fetch_orders_by_user_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Orders WHERE user_id = %s", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

# Функция для получения всех категорий
async def fetch_categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Categories")
    categories = cursor.fetchall()
    conn.close()
    return categories

# Функция для добавления категории
async def add_category(category_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Categories (category) VALUES (%s)", (category_name,))
    conn.commit()
    category_id = cursor.lastrowid  # Получаем ID новой категории
    conn.close()
    return category_id

async def update_order_status(order_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", (status, order_id))
    conn.commit()
    conn.close()

async def fetch_order_by_id(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order


# Функция для выгрузки заказов в CSV
async def export_orders():
    orders = await fetch_orders()
    file_path = "orders.csv"
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Order ID", "User ID", "Order Date", "Total Amount", "Status", "Items Details", "Type of Delivery", "Address Delivery", "Phone", "Username"])
        for order in orders:
            writer.writerow([
                order["order_id"],
                order["user_id"],
                order["order_date"],
                order["total_amount"],
                order["status"],
                order["items_details"],
                order["type_of_delivery"],
                order["address_delivery"],
                order["phone"],
                order["username"]
            ])
    return file_path

# Функция для выгрузки категорий в CSV
async def export_categories():
    categories = await fetch_categories()
    file_path = "categories.csv"
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Category ID", "Category Name"])
        for category in categories:
            writer.writerow([category["category_id"], category["category"]])
    return file_path

async def add_product(name, description, price, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO Products (name, description, price, category_id)
    VALUES (%s, %s, %s, %s)
    """, (name, description, price, category_id))
    conn.commit()
    conn.close()

async def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Products WHERE product_id = %s", (product_id,))
    conn.commit()
    conn.close()

async def export_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Products")
    products = cursor.fetchall()
    conn.close()

    file_path = "products.csv"
    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Product ID", "Name", "Description", "Price", "Category ID"])
        for product in products:
            writer.writerow([
                product["product_id"],
                product["name"],
                product["description"],
                product["price"],
                product["category_id"]
            ])
    return file_path

# Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id in ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.button(text="Добавить продукт", callback_data="add_product")
        builder.button(text="Удалить продукт", callback_data="delete_product")
        builder.button(text="Выгрузить список продуктов", callback_data="export_products")
        builder.button(text="Выгрузить список заказов", callback_data="export_orders")
        builder.button(text="Получить заказ по ID", callback_data="get_order_by_id")
        builder.button(text="Получить заказы по user_id", callback_data="get_orders_by_user_id")
        builder.button(text="Изменить статус заказа", callback_data="update_order_status")
        builder.button(text="Выгрузить список категорий", callback_data="export_categories")
        builder.button(text="Добавить категорию", callback_data="add_category")
        builder.adjust(1)
        await message.answer("Админ-меню:", reply_markup=builder.as_markup())
    else:
        await message.answer("У вас нет доступа к этой команде.")


# Обработка callback-запросов
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_ID:
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
    elif callback.data == "export_orders":
        file_path = await export_orders()
        file = FSInputFile(file_path)
        await callback.message.answer_document(file)
    elif callback.data == "get_order_by_id":
        await callback.message.answer("Отправьте ID заказа")
    elif callback.data == "get_orders_by_user_id":
        await callback.message.answer("Отправьте user_id")
    elif callback.data == "update_order_status":
        await callback.message.answer("Отправьте данные в формате: ID заказа, Новый статус")
    elif callback.data == "export_categories":
        file_path = await export_categories()
        file = FSInputFile(file_path)
        await callback.message.answer_document(file)
    elif callback.data == "add_category":
        await callback.message.answer("Отправьте имя категории")
    await callback.answer()


# Обработка сообщений
@dp.message()
async def process_message(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = message.text.split(", ")
    if len(text) == 4:
        # Добавление продукта
        try:
            name, description, price, category_id = text
            await add_product(name, description, float(price), int(category_id))
            await message.answer("Продукт добавлен!")
        except ValueError:
            await message.answer("Ошибка в формате данных.")
    elif len(text) == 2 and text[0].isdigit():
        # Изменение статуса заказа
        order_id, status = text
        await update_order_status(int(order_id), status)
        await message.answer(f"Статус заказа {order_id} изменён на '{status}'!")
    elif len(text) == 1:
        if text[0].isdigit():
            # Если отправлен один ID, это может быть order_id, user_id или product_id
            order_id = int(text[0])
            order = await fetch_order_by_id(order_id)
            if order:
                await message.answer(f"Заказ:\n{order}")
            else:
                user_id = order_id
                orders = await fetch_orders_by_user_id(user_id)
                if orders:
                    await message.answer(f"Заказы для user_id {user_id}:\n{orders}")
                else:
                    product_id = order_id
                    await delete_product(product_id)
                    await message.answer(f"Продукт с ID {product_id} удалён!")
        else:
            # Добавление категории
            category_name = text[0]
            category_id = await add_category(category_name)
            await message.answer(f"Категория добавлена! ID: {category_id}")
    else:
        await message.answer("Неверный формат ввода.")


# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())