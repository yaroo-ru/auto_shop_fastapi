from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import random

def fill_rastamozhka_form(age: str, engine: str, power: int, volume: int, price: int, curr: str, max_retries=3):
    """
    Улучшенная версия функции для расчета растаможки с надежным драйвером как в парсере Encar
    
    Параметры:
    age (str): Возрастная категория ("0-3", "3-5", "5-7", "7+")
    engine (str): Тип двигателя ("gasoline", "diesel", "hybrid", "electric")
    power (int): Мощность двигателя (л.с.)
    volume (int): Объем двигателя (см³)
    price (int): Стоимость автомобиля
    curr (str): Валюта ("krw" - вона, "usd" - доллар, "eur" - евро)
    max_retries (int): Максимальное количество попыток (по умолчанию 3)
    
    Возвращает:
    str: Сумма с растаможкой или сообщение об ошибке
    """
    # Список user-agent для ротации
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ]
    
    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            print(f"\n[Попытка {attempt}/{max_retries}] Расчет растаможки...")
            
            # Настройка драйвера как в парсере Encar
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument(f"user-agent={random.choice(user_agents)}")
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            wait = WebDriverWait(driver, 20)
            
            # Маскируем WebDriver
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.navigator.chrome = {
                        runtime: {},
                    };
                """
            })
            
            print("🌐 Загрузка страницы калькулятора...")
            try:
                driver.get("https://calcus.ru/rastamozhka-auto")
                time.sleep(random.uniform(1, 3))
            except TimeoutException:
                print("⚠️ Страница загружалась слишком долго, продолжаем...")
            
            # Проверка на блокировку
            if any(phrase in driver.page_source for phrase in ["Доступ ограничен", "Ошибка 403"]):
                print("🛑 Обнаружена блокировка, меняем user-agent...")
                new_agent = random.choice(user_agents)
                driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": new_agent})
                driver.refresh()
                time.sleep(3)
            
            # Ожидание загрузки формы
            try:
                wait.until(EC.presence_of_element_located((By.NAME, "power")))
                print("✅ Форма загружена")
            except TimeoutException:
                if "Калькулятор растаможки" not in driver.title:
                    raise Exception("Не удалось загрузить форму расчета")
            
            # Заполнение полей формы с повторными попытками
            fields = [
                ("owner", "1", "select"),  # Физическое лицо
                ("age", age, "select"),
                ("engine", engine, "select"),
                ("power", str(int(power)), "input"),
                ("value", str(int(volume)), "input"),
                ("price", str(int(price)), "input"),
                ("curr", curr, "select")
            ]
            
            for field_name, value, field_type in fields:
                for try_num in range(3):
                    try:
                        element = wait.until(EC.presence_of_element_located((By.NAME, field_name)))
                        if field_type == "select":
                            Select(element).select_by_value(value)
                        else:
                            element.clear()
                            element.send_keys(value)
                        break
                    except Exception as e:
                        if try_num == 2:
                            raise
                        time.sleep(0.5)
                time.sleep(random.uniform(0.1, 0.5))
            
            # Отправка формы
            submit_btn = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "calc-submit")))
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", submit_btn)
            print("📤 Форма отправлена")
            
            # Ожидание результата
            result = None
            start_time = time.time()
            while time.time() - start_time < 10:
                try:
                    total_div = driver.find_element(
                        By.XPATH,
                        '//div[text()="Стоимость автомобиля + растаможка"]/..//div[@class="calc-result-value result-placeholder-total2"]'
                    )
                    if total_div.text.strip():
                        result = total_div.text.strip()
                        print(f"🎉 Результат: {result}")
                        return result
                except:
                    pass
                
                # Проверка на ошибки
                if "Ошибка" in driver.page_source:
                    error_elements = driver.find_elements(By.CLASS_NAME, "error-message")
                    if error_elements:
                        raise Exception(f"Ошибка расчета: {error_elements[0].text[:100]}")
                
                time.sleep(0.5)
            
            raise Exception("Не удалось получить результат после отправки формы")
        
        except Exception as e:
            print(f"⚠️ Ошибка: {str(e)[:200]}")
            if attempt == max_retries:
                return f"❌ Не удалось рассчитать растаможку после {max_retries} попыток. Последняя ошибка: {str(e)[:200]}"
            
            # Случайная задержка перед повторной попыткой
            delay = random.uniform(2, 5)
            print(f"⏳ Ожидание {delay:.1f} секунд перед повторной попыткой...")
            time.sleep(delay)
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    return "❌ Неизвестная ошибка при расчете растаможки"

# Пример использования (можно раскомментировать для теста)
# result = fill_rastamozhka_form(
#     age="3-5",
#     engine="gasoline",
#     power=150,
#     volume=2000,
#     price=20000000,
#     curr="krw"
# )
# print("Итоговый результат:", result)