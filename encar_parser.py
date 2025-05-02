import random
import time
from datetime import datetime
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import requests
import json 
import os
import tempfile
from selenium.webdriver.common.action_chains import ActionChains


class CaptchaHandler:
    def __init__(self):
        self.capsolver_api_key = "CAP-E5C0999A221B46886AD2CC37355ADE59"
        self.block_phrases = [
            "비정상적인 트래픽",
            "접속이 제한되었습니다",
            "현재 접속이 제한되었습니다",
            "시스템에서 비정상적인 트래픽이 감지되어"
        ]
        self.recaptcha_sitekey = "6LdNq5wmAAAAAFbrCxo9h6CnZF2Zcl6T39tqvwbS"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]

    def detect_block_page(self, driver):
        """Improved block page detection"""
        try:
            page_source = driver.page_source
            return any(phrase in page_source for phrase in self.block_phrases)
        except:
            return False

    def bypass_block_page(self, driver):
        """Comprehensive block page bypass"""
        print("🛑 Block page detected, applying bypass techniques...")

        try:
            # 1. Try to solve the reCAPTCHA if present
            if self.solve_recaptcha_v2(driver, driver.current_url):
                time.sleep(3)
                if not self.detect_block_page(driver):
                    return True

            # 2. Try to click the home button
            try:
                home_button = driver.find_element(By.CSS_SELECTOR, ".ClientVerificationBlockedPage_btn_home__FyBHP button")
                home_button.click()
                print("🔘 Home button clicked")
                time.sleep(3)
                return True
            except:
                pass

            # 3. Try to reload with random delay
            for _ in range(3):
                delay = random.uniform(5, 15)
                print(f"🔄 Reloading page after {delay:.1f} seconds...")
                time.sleep(delay)
                driver.execute_script("window.location.reload()")
                time.sleep(5)

                if not self.detect_block_page(driver):
                    return True

            # 4. Try to change user agent and reload
            new_user_agent = random.choice(self.user_agents)
            print(f"🔄 Changing user agent to: {new_user_agent[:50]}...")
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": new_user_agent})
            driver.execute_script("window.location.reload()")
            time.sleep(5)

            return not self.detect_block_page(driver)

        except Exception as e:
            print(f"⚠️ Bypass error: {str(e)[:200]}")
            return False

    def solve_recaptcha_v2(self, driver, page_url):
        """Enhanced reCAPTCHA v2 solver with multiple approaches"""
        try:
            print("🔍 Attempting to solve reCAPTCHA v2...")

            # Approach 1: Use Capsolver API
            if self._solve_with_capsolver(driver, page_url):
                return True

            # Approach 2: Manual challenge solving (if checkbox exists)
            if self._solve_manual_checkbox(driver):
                return True

            return False

        except Exception as e:
            print(f"⚠️ reCAPTCHA solving error: {str(e)[:200]}")
            return False

    def _solve_with_capsolver(self, driver, page_url):
        """Solve using Capsolver API"""
        try:
            print("🔧 Trying Capsolver API solution...")

            payload = {
                "clientKey": self.capsolver_api_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": self.recaptcha_sitekey,
                    "isInvisible": False,
                    "userAgent": driver.execute_script("return navigator.userAgent")
                }
            }

            # Create task
            response = requests.post(
                "https://api.capsolver.com/createTask",
                json=payload,
                timeout=60
            )
            task_id = response.json().get("taskId")
            print(f"🔄 Task created with ID: {task_id}")

            # Wait for solution
            for _ in range(20):
                time.sleep(3)
                result = requests.post(
                    "https://api.capsolver.com/getTaskResult",
                    json={"clientKey": self.capsolver_api_key, "taskId": task_id}
                ).json()

                if result.get("status") == "ready":
                    token = result.get("solution", {}).get("gRecaptchaResponse")
                    print("✅ Got captcha token, applying...")

                    # Inject token in multiple ways
                    injection_success = False
                    injection_scripts = [
                        # Standard method
                        'document.getElementById("g-recaptcha-response").value = arguments[0];',

                        # Alternative methods
                        'if(typeof ___grecaptcha_cfg !== "undefined"){ '
                        'Object.values(___grecaptcha_cfg.clients).forEach(client=>{ '
                        'try{ client.L.L.callback(arguments[0]) }catch(e){} }); }',

                        'if(typeof grecaptcha !== "undefined"){ '
                        'grecaptcha.getResponse = function(){ return arguments[0] }; }'
                    ]

                    for script in injection_scripts:
                        try:
                            driver.execute_script(script, token)
                            time.sleep(1)
                            injection_success = True
                        except:
                            continue

                    if injection_success:
                        print("✔️ Token injected successfully")
                        time.sleep(2)
                        return True

            print("❌ Failed to get valid solution from Capsolver")
            return False

        except Exception as e:
            print(f"⚠️ Capsolver error: {str(e)[:200]}")
            return False

    def _solve_manual_checkbox(self, driver):
        """Try to solve by clicking the checkbox manually"""
        try:
            print("🔧 Trying manual checkbox solution...")

            # Switch to recaptcha iframe
            iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2']")
            if not iframes:
                return False

            driver.switch_to.frame(iframes[0])

            # Click the checkbox
            checkbox = driver.find_element(By.ID, "recaptcha-anchor")
            checkbox.click()
            print("🔘 Checkbox clicked")

            # Switch back to main content
            driver.switch_to.default_content()
            time.sleep(3)

            # Check if challenge appears
            if self._handle_challenge_if_needed(driver):
                return True

            return True  # Assume success if no challenge appeared

        except Exception as e:
            print(f"⚠️ Manual checkbox error: {str(e)[:200]}")
            return False

    def _handle_challenge_if_needed(self, driver):
        """Handle the image/audio challenge if it appears"""
        try:
            # Check if challenge iframe appeared
            challenge_frame = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='api2/bframe']")
            if not challenge_frame:
                return True  # No challenge appeared

            print("🖼️ Challenge detected, trying to solve...")
            return False  # For now, return False as we can't solve image challenges automatically

        except:
            return False

    def solve_captcha(self, driver, page_url):
        """Main captcha solving flow with improved logic"""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"\n🛡️ Captcha solving attempt {attempt}/{max_attempts}")

            # First check for block page
            if self.detect_block_page(driver):
                if self.bypass_block_page(driver):
                    print("🎉 Block page bypassed!")
                    return True
                continue

            # Then try to solve reCAPTCHA if present
            if "g-recaptcha" in driver.page_source:
                if self.solve_recaptcha_v2(driver, page_url):
                    print("🎉 reCAPTCHA solved!")
                    time.sleep(2)
                    return True
                continue

            # If neither, assume we're good
            return True

        print(f"❌ Failed to solve after {max_attempts} attempts")
        return False

def setup_driver():
    """Configure Chrome driver with optimal settings"""
    options = Options()
    # Режим без графического интерфейса (если запускается на сервере)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Укажите путь к chromedriver, если он не находится в PATH
    driver = Chrome(options=options)

    return driver


def parse_encar(url, max_retries=5):
    """Полноценный парсер Encara с обработкой ошибок и повторными попытками"""
    driver = None
    captcha_handler = CaptchaHandler()
    result_template = {
        "Manufacture date (raw)": "Not found",
        "Manufacture date": "Not found",
        "Age category": "Undefined",
        "Engine volume": "Not found",
        "Engine type": "Not found",
        "Mileage": "Not found",
        "Price (₩)": "Not found"
    }

    for attempt in range(1, max_retries + 1):
        print(f"\n[Attempt {attempt}/{max_retries}] Processing {url}")
        result = result_template.copy()

        try:
            # Инициализация драйвера
            driver = setup_driver()
            driver.set_page_load_timeout(45)
            wait = WebDriverWait(driver, 20)

            # Загрузка страницы
            print("🌐 Loading page...")
            try:
                driver.get(url)
            except TimeoutException:
                print("⚠️ Page load timeout, continuing with current content")

            # Обработка защиты
            if not captcha_handler.solve_captcha(driver, url):
                print("⚠️ Failed to bypass protection")
                raise Exception("Captcha bypass failed")

            # Ожидание основных элементов
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                print("✅ Main content loaded")
            except TimeoutException:
                print("⚠️ Main content not loaded")
                raise

            # Сохранение страницы для отладки
            with open(f"debug_page_{attempt}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)

            # Закрытие модальных окон
            driver.execute_script("""
                document.querySelectorAll('div[class*="modal"], div[class*="popup"]').forEach(el => {
                    el.style.display = 'none';
                });
            """)

            # Нажатие кнопки "Подробнее"
            print("🔍 Clicking details button...")
            for click_attempt in range(3):
                try:
                    details_btn = wait.until(EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'button[class*="DetailSummary_btn_detail"]')
                    ))
                    details_btn.click()
                    print(f"✅ Details button clicked (attempt {click_attempt + 1})")
                    break
                except Exception as e:
                    print(f"⚠️ Details button click failed (attempt {click_attempt + 1}): {str(e)}")
                    time.sleep(1)
            else:
                print("⚠️ Failed to click details button after 3 attempts")

            # Ожидание загрузки характеристик
            try:
                wait.until(lambda d: d.execute_script(
                    'return document.querySelector("ul[class*=DetailSpec_list_default]") !== null'
                ))
                print("📊 Specifications loaded")
            except TimeoutException:
                print("⚠️ Specifications failed to load")

            # Парсинг данных
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Извлечение данных из списка характеристик
            spec_list = soup.find("ul", class_=lambda x: x and "DetailSpec_list_default" in x)
            if spec_list:
                items = spec_list.find_all("li")
                if len(items) > 1:
                    date_text = items[1].find("span").get_text(strip=True)
                    result["Manufacture date (raw)"] = date_text
                    result["Manufacture date"], result["Age category"] = process_date(date_text)
                if len(items) > 3:
                    engine_volume = items[3].find("span").get_text(strip=True)
                    result["Engine volume"] = engine_volume.replace(",", "").replace("cc", "").strip()
                if len(items) > 4:
                    engine_type = items[4].find("span").get_text(strip=True)
                    result["Engine type"] = translate_engine_type(engine_type)

            # Извлечение пробега
            try:
                mileage_label = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//dt[contains(text(), '주행거리')]"))
                )
                mileage_value = mileage_label.find_element(By.XPATH, "./following-sibling::dd[1]")
                result["Mileage"] = mileage_value.text.strip()
                print(f"🛣️ Mileage extracted: {result['Mileage']}")
            except Exception as e:
                print(f"⚠️ Mileage extraction failed: {str(e)}")

            # Извлечение цены
            for price_attempt in range(3):
                try:
                    price_element = wait.until(
                        EC.presence_of_element_located((By.CLASS_NAME, "DetailLeadCase_point__vdG4b"))
                    )
                    price_text = price_element.get_attribute("textContent").strip()
                    price_value = int(float(price_text.replace(",", "").replace("만원", "")) * 10000)
                    result["Price (₩)"] = f"{price_value}"
                    print(f"💰 Price extracted: {result['Price (₩)']}")
                    break
                except Exception as e:
                    print(f"⚠️ Price extraction failed (attempt {price_attempt + 1}): {str(e)}")
                    time.sleep(1)

            # Валидация данных
            if result["Price (₩)"] == "Not found" or result["Engine volume"] == "Not found":
                raise ValueError("Key data not found")

            print("🎉 Data successfully extracted!")
            return result

        except Exception as e:
            print(f"⚠️ Attempt {attempt} failed: {str(e)}")
            if attempt < max_retries:
                print(f"🔄 Retrying in 3 seconds...")
                time.sleep(3)
            
            # Сохранение скриншота при ошибке
            try:
                driver.save_screenshot(f"error_screenshot_{attempt}.png")
                print("📸 Saved error screenshot")
            except:
                pass

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    print(f"❌ Failed after {max_retries} attempts")
    return None


def extract_data(soup, driver):
    """Extract all required data from page"""
    result = {
        "Manufacture date (raw)": "Not found",
        "Manufacture date": "Not found",
        "Age category": "Undefined",
        "Engine volume": "Not found",
        "Engine type": "Not found",
        "Mileage": "Not found",
        "Price (₩)": "Not found"
    }

    # Extract from spec list
    spec_list = soup.find("ul", class_="DetailSpec_list_default__Gx+ZA")
    if spec_list:
        items = spec_list.find_all("li")
        if len(items) > 1:
            date_text = items[1].find("span").get_text(strip=True)
            result["Manufacture date (raw)"] = date_text
            result["Manufacture date"], result["Age category"] = process_date(date_text)
        if len(items) > 3:
            engine_volume = items[3].find("span").get_text(strip=True)
            result["Engine volume"] = engine_volume.replace(",", "").replace("cc", "").strip()
        if len(items) > 4:
            engine_type = items[4].find("span").get_text(strip=True)
            result["Engine type"] = translate_engine_type(engine_type)

    # Extract mileage - ADD THIS SECTION
    try:
        mileage_label = driver.find_element(By.XPATH, "//dt[text()='주행거리']")
        mileage_value = mileage_label.find_element(By.XPATH, "following-sibling::dd[1]")
        result["Mileage"] = mileage_value.text
    except Exception as e:
        print(f"⚠️ Failed to extract mileage: {str(e)}")

    # Extract price
    for _ in range(3):
        try:
            price_element = driver.find_element(By.CLASS_NAME, "DetailLeadCase_point__vdG4b")
            price_text = price_element.get_attribute("textContent").strip().replace(",", "").replace("만원", "")
            price_value = int(float(price_text) * 10000)
            result["Price (₩)"] = f"{price_value}"
            break
        except:
            time.sleep(1)
            continue

    return result


def process_date(date_str):
    try:
        year_part = int(date_str[:2])
        month_part = int(date_str[4:6])
        full_year = 2000 + year_part
        formatted_date = f"{full_year}-{month_part:02d}"

        current_year = datetime.now().year
        age = current_year - full_year

        if age < 3:
            category = "0-3"
        elif 3 <= age < 5:
            category = "3-5"
        elif 5 <= age < 7:
            category = "5-7"
        else:
            category = "7-0"

        return formatted_date, category
    except Exception:
        return "Date error", "Undefined"


def translate_engine_type(korean_type):
    translations = {
        "가솔린": "1",
        "디젤": "2",
        "가솔린+전기": "3",
        "전기": "4",
        "LPG": "1",
        "LPG(일반인 구입)LPG 자세히보기": "1",
        "수소": "2"
    }
    return translations.get(korean_type, korean_type)