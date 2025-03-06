import mysql.connector
import os

def connect():
    conn = mysql.connector.connect(
        host=os.getenv("HOST_MSQL"),
        user=os.getenv("USER_MSQL"),
        password=os.getenv("PASSWORD_MSQL")
    )

    return conn

def create_db(connection) -> bool:
    conn = connection

    try:
        cursor = conn.cursor()

        cursor.execute("CREATE DATABASE IF NOT EXISTS auto_shop")
        cursor.execute("USE auto_shop")

        # Таблица Users
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INT PRIMARY KEY,          -- Уникальный идентификатор пользователя
            first_name VARCHAR(255),          -- Имя пользователя
            last_name VARCHAR(255),           -- Фамилия пользователя
            username VARCHAR(255),            -- Имя пользователя в Telegram
            language_code VARCHAR(10),        -- Код языка пользователя
            allows_write_to_pm BOOLEAN        -- Разрешение на отправку сообщений
        );
        """)

        # Таблица Orders
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            order_id INT PRIMARY KEY,
            user_id INT,
            order_date DATETIME,
            total_amount DECIMAL(10, 2),
            status VARCHAR(50),
            items_details JSON,
            type_of_delivery VARCHAR(50),
            address_delivery TEXT,
            phone VARCHAR(15),
            username VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        )
        """)

        # Таблица Categories
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Categories (
            category_id INT PRIMARY KEY,
            category VARCHAR(255)
        )
        """)

        # Таблица Products
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Products (
            product_id INT PRIMARY KEY,
            name VARCHAR(255),
            description TEXT,
            price DECIMAL(10, 2),
            category_id INT,
            FOREIGN KEY (category_id) REFERENCES Categories(category_id)
        )
        """)

        # Таблица Cart (1 запись на пользователя)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Cart (
            user_id INT PRIMARY KEY,  -- У каждого пользователя только одна корзина
            items_details JSON,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)  -- Связь с пользователем
        )
        """)

        cursor.close()
        conn.close()

        return "База данных успешно создана"
    
    except Exception as e:
        return f"Ошибка при создании базы данных: {e}"


create_db(connect())