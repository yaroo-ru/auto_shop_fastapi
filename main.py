from fastapi import FastAPI, Request, HTTPException, Query, Header
import json
from urllib.parse import parse_qs
import uuid
import mysql.connector
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI()

# Хранилище сессий (в памяти)
sessions = {}

# Функция для подключения к базе данных
def connect():
    conn = mysql.connector.connect(
        host=os.getenv("HOST_MSQL"),
        user=os.getenv("USER_MSQL"),
        password=os.getenv("PASSWORD_MSQL"),
        database=os.getenv("DATABASE_MSQL")
    )
    return conn

# Модель товара
class Product(BaseModel):
    product_id: int
    name: str
    description: str
    price: float
    category_id: int

# Модель для элемента корзины
class CartItem(BaseModel):
    product_id: int
    quantity: int

# Модель для корзины
class Cart(BaseModel):
    user_id: int
    items_details: List[CartItem]

class InitData(BaseModel):
    user: str  # JSON-строка с данными пользователя
    chat_instance: str
    chat_type: str
    auth_date: str
    hash: str
    
class Order(BaseModel):
    order_id: int
    user_id: int
    order_date: datetime
    total_amount: float
    status: str
    items_details: List[CartItem]  # Список товаров в заказе
    type_of_delivery: str
    address_delivery: str
    phone: str
    username: str

# Функция для парсинга Init Data
def parse_init_data(init_data):
    # Декодируем строку
    parsed_data = parse_qs(init_data)
    # Извлекаем данные пользователя
    user_data = parsed_data.get("user", [""])[0]  # JSON-строка
    # Преобразуем JSON-строку в словарь
    user = json.loads(user_data)
    return user

def ensure_user_exists(conn, user_id, first_name, last_name, username, language_code, allows_write_to_pm):
    cursor = conn.cursor()

    # Проверяем, существует ли пользователь
    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        # Если пользователя нет, создаём новую запись
        cursor.execute("""
        INSERT INTO users (user_id, first_name, last_name, username, language_code, allows_write_to_pm)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, first_name, last_name, username, language_code, allows_write_to_pm))

        # Создаём пустую корзину для пользователя
        cursor.execute("""
        INSERT INTO Cart (user_id, items_details)
        VALUES (%s, %s)
        """, (user_id, json.dumps([])))  # Пустой список товаров

        conn.commit()

    cursor.close()

def get_product_price(product_id: int) -> float:
    conn = connect()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT price FROM Products WHERE product_id = %s", (product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        raise HTTPException(status_code=404, detail=f"Товар с ID {product_id} не найден")

    return product["price"]

# Эндпоинт для получения всех товаров с фильтрацией и сортировкой
@app.get("/products", response_model=list[Product])
def get_all_products(
    category_id: Optional[int] = Query(None, description="Фильтр по category_id"),
    name: Optional[str] = Query(None, description="Фильтр по имени (частичное совпадение)"),
    sort_by: Optional[str] = Query(None, description="Поле для сортировки (например, price или category)"),
    order: Optional[str] = Query("asc", description="Порядок сортировки: asc (по возрастанию) или desc (по убыванию)")
):
    try:
        conn = connect()
        cursor = conn.cursor(dictionary=True)

        # Базовый запрос
        query = """
        SELECT p.product_id, p.name, p.description, p.price, p.category_id, c.category
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE 1=1
        """

        # Добавляем фильтр по category_id, если он указан
        if category_id is not None:
            query += f" AND p.category_id = {category_id}"

        # Добавляем фильтр по имени, если оно указано
        if name is not None:
            query += f" AND p.name LIKE '%{name}%'"

        # Определяем поле для сортировки
        if sort_by:
            sort_field = sort_by
        else:
            sort_field = "p.product_id"  # Сортировка по умолчанию

        # Добавляем сортировку
        if order.lower() not in ["asc", "desc"]:
            raise HTTPException(status_code=400, detail="Порядок сортировки должен быть 'asc' или 'desc'")
        query += f" ORDER BY {sort_field} {order}"

        # Выполняем запрос
        cursor.execute(query)
        products = cursor.fetchall()

        cursor.close()
        conn.close()

        return products

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении товаров: {str(e)}")



# Эндпоинт для создания сессии
@app.post("/start_session")
async def start_session(init_data: InitData):
    # Декодируем Init Data
    user = json.loads(init_data.user)
    user_id = user.get("id")
    first_name = user.get("first_name")
    last_name = user.get("last_name")
    username = user.get("username")
    language_code = user.get("language_code")
    allows_write_to_pm = user.get("allows_write_to_pm")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id не найден в Init Data")

    # Подключаемся к базе данных
    conn = connect()
    cursor = conn.cursor()

    # Проверяем и создаём пользователя, если его нет
    ensure_user_exists(conn, user_id, first_name, last_name, username, language_code, allows_write_to_pm)

    # Создаем уникальный session_id
    session_id = str(uuid.uuid4())

    # Сохраняем Init Data в сессии
    sessions[session_id] = {"init_data": init_data.json(), "user_id": user_id}

    cursor.close()
    conn.close()

    # Возвращаем session_id клиенту
    return {"session_id": session_id}


# Эндпоинт для получения корзины
@app.post("/cart")
async def get_cart(session_id: str = Header(..., alias="X-Session-ID")):
    # Находим сессию по session_id
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    # Извлекаем user_id из сессии
    user_id = session.get("user_id")

    # Подключаемся к базе данных
    conn = connect()
    cursor = conn.cursor(dictionary=True)

    # Получаем корзину из базы данных
    query = "SELECT * FROM Cart WHERE user_id = %s"
    cursor.execute(query, (user_id,))
    cart = cursor.fetchone()

    cursor.close()
    conn.close()

    if not cart:
        raise HTTPException(status_code=404, detail="Корзина не найдена")

    # Преобразуем строку JSON в список словарей
    items_details = json.loads(cart["items_details"])

    # Создаем список объектов CartItem
    cart["items_details"] = [CartItem(**item) for item in items_details]
    return {"user_id": user_id, "cart": cart}


# Эндпоинт для обновления корзины
@app.post("/cart/update")
async def update_cart(
    items_details: List[CartItem],
    session_id: str = Header(..., alias="X-Session-ID")
):
    # Находим сессию по session_id
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    # Извлекаем user_id из сессии
    user_id = session.get("user_id")

    # Подключаемся к базе данных
    conn = connect()
    cursor = conn.cursor(dictionary=True)

    # Обновляем корзину в базе данных
    query = """
    INSERT INTO Cart (user_id, items_details)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE items_details = %s
    """
    cursor.execute(query, (user_id, json.dumps([item.dict() for item in items_details]), json.dumps([item.dict() for item in items_details])))
    conn.commit()

    cursor.close()
    conn.close()

    return {"user_id": user_id, "message": "Корзина обновлена"}

@app.get("/orders")
async def get_orders(session_id: str = Header(..., alias="X-Session-ID")):
    # Находим сессию по session_id
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    # Извлекаем user_id из сессии
    user_id = session.get("user_id")

    # Подключаемся к базе данных
    conn = connect()
    cursor = conn.cursor(dictionary=True)

    # Получаем заказы пользователя
    cursor.execute("SELECT * FROM Orders WHERE user_id = %s", (user_id,))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    if not orders:
        raise HTTPException(status_code=404, detail="Заказы не найдены")

    # Преобразуем строку JSON в список объектов CartItem
    for order in orders:
        order["items_details"] = [CartItem(**item) for item in json.loads(order["items_details"])]

    return {"user_id": user_id, "orders": orders}

@app.post("/orders/create")
async def create_order(
    type_of_delivery: str,
    address_delivery: str,
    phone: str,
    session_id: str = Header(..., alias="X-Session-ID")
):
    # Находим сессию по session_id
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    # Извлекаем user_id из сессии
    user_id = session.get("user_id")

    # Подключаемся к базе данных
    conn = connect()
    cursor = conn.cursor(dictionary=True)

    # Получаем корзину пользователя
    cursor.execute("SELECT * FROM Cart WHERE user_id = %s", (user_id,))
    cart = cursor.fetchone()

    if not cart:
        raise HTTPException(status_code=404, detail="Корзина не найдена")

    # Извлекаем данные корзины
    items_details = json.loads(cart["items_details"])

    # Рассчитываем общую сумму заказа
    total_amount = sum(item["quantity"] * get_product_price(item["product_id"]) for item in items_details)

    # Получаем username из сессии
    init_data = json.loads(session["init_data"])
    username = init_data.get("username", "")

    # Генерируем order_id (если он не автоинкрементный)
    cursor.execute("SELECT MAX(order_id) AS max_order_id FROM Orders")
    max_order_id = cursor.fetchone()["max_order_id"]
    order_id = (max_order_id or 0) + 1  # Увеличиваем на 1

    # Создаем заказ
    cursor.execute("""
    INSERT INTO Orders (
        order_id, user_id, order_date, total_amount, status, items_details,
        type_of_delivery, address_delivery, phone, username
    )
    VALUES (%s, %s, NOW(), %s, 'pending', %s, %s, %s, %s, %s)
    """, (
        order_id, user_id, total_amount, json.dumps(items_details),
        type_of_delivery, address_delivery, phone, username
    ))

    conn.commit()

    # Очищаем корзину после создания заказа
    cursor.execute("UPDATE Cart SET items_details = %s WHERE user_id = %s", (json.dumps([]), user_id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Заказ успешно создан", "order_id": order_id}


# Запуск приложения
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)