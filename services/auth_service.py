import os
import time
import json
import logging
import traceback
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        # Константы
        self.COOKIES_FILE = "pocket_option_cookies.json"
        self.COOKIES_EXPIRY_FILE = "cookies_expiry.json"
        self.LOGIN_URL = "https://pocketoption.com/en/sign-in/"
        self.API_URL = "https://pocketoption.com/api/v2/"
        self.TIMEOUT = 30
        
        # Пути к Chrome и ChromeDriver
        self.CHROME_PATHS = [
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Users\\Administrator\\Desktop\\chrome-win64\\chrome.exe"
        ]
        
        self.CHROMEDRIVER_PATHS = [
            r"C:\\Users\\Administrator\\Desktop\\chromedriver-win64\\chromedriver.exe",
            r".\\chromedriver.exe",
            r"chromedriver.exe"
        ]
        
        # Состояние
        self.driver = None
        self._is_logged_in = False
        self._ssid = None
        self._api_session = requests.Session()

    def _setup_driver(self, headless=False):
        """Настройка и запуск Chrome драйвера"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless=new")
            
            # Базовые настройки
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User-Agent для имитации реального браузера
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Отключение автоматизации
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Поиск Chrome
            chrome_found = False
            for path in self.CHROME_PATHS:
                if os.path.exists(path):
                    chrome_options.binary_location = path
                    chrome_found = True
                    logger.info(f"✅ Chrome найден по пути: {path}")
                    break
            
            if not chrome_found:
                logger.error("❌ Chrome не найден в стандартных местах установки")
                return False
            
            # Поиск ChromeDriver
            driver_found = False
            service = None
            for path in self.CHROMEDRIVER_PATHS:
                if os.path.exists(path):
                    service = Service(path)
                    driver_found = True
                    logger.info(f"✅ ChromeDriver найден по пути: {path}")
                    break
            
            if not driver_found:
                logger.error("❌ ChromeDriver не найден")
                return False
            
            # Инициализация драйвера
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(self.TIMEOUT)
            self.driver.implicitly_wait(10)
            
            logger.info("✅ Драйвер успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при настройке драйвера: {e}")
            return False

    def _save_cookies(self, cookies):
        """Сохранение cookies в файлы JSON"""
        try:
            # Фильтрация cookies
            filtered_cookies = []
            for cookie in cookies:
                if 'expiry' in cookie:
                    try:
                        int(cookie['expiry'])
                        filtered_cookies.append(cookie)
                    except:
                        continue
                else:
                    filtered_cookies.append(cookie)
            
            # Сохранение cookies
            with open(self.COOKIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(filtered_cookies, f, ensure_ascii=False, indent=2)
            
            # Сохранение времени истечения (24 часа)
            expiry_time = datetime.now() + timedelta(hours=24)
            with open(self.COOKIES_EXPIRY_FILE, 'w') as f:
                json.dump({"expiry": expiry_time.isoformat()}, f)
            
            logger.info(f"✅ Cookies сохранены: {len(filtered_cookies)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении cookies: {e}")
            return False

    def _load_cookies(self):
        """Загрузка cookies из файлов JSON"""
        try:
            if not os.path.exists(self.COOKIES_FILE):
                return None
                
            with open(self.COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            return cookies
            
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке cookies: {e}")
            return None

    def _check_cookies_expiry(self):
        """Проверка срока действия cookies через файл JSON"""
        try:
            if not os.path.exists(self.COOKIES_EXPIRY_FILE):
                return False
                
            with open(self.COOKIES_EXPIRY_FILE, 'r') as f:
                expiry_data = json.load(f)
                expiry_time = datetime.fromisoformat(expiry_data["expiry"])
                return datetime.now() < expiry_time
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке срока cookies: {e}")
            return False

    def start_auth_process(self):
        """Запуск процесса авторизации"""
        try:
            # Инициализация драйвера если нужно
            if not self.driver:
                if not self._setup_driver():
                    return False
            
            # Проверка существующих cookies
            if self._check_cookies_expiry():
                cookies = self._load_cookies()
                if cookies:
                    self.driver.get("https://pocketoption.com")
                    for cookie in cookies:
                        self.driver.add_cookie(cookie)
                    self.driver.refresh()
                    
                    # Проверка успешности авторизации
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "user-avatar"))
                        )
                        self._is_logged_in = True
                        logger.info("✅ Авторизация через cookies успешна")
                        return True
                    except:
                        logger.warning("⚠️ Авторизация через cookies не удалась")
            
            # Если cookies недействительны или их нет - открываем страницу логина
            self.driver.get(self.LOGIN_URL)
            logger.info("🌐 Открыта страница логина. Требуется ручной вход")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка в процессе авторизации: {e}")
            return False

    def confirm_auth(self):
        """Подтверждение успешной авторизации"""
        try:
            if not self.driver:
                logger.error("❌ Драйвер не инициализирован")
                return False
            
            # Проверка успешности авторизации
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-avatar"))
            )
            
            # Сохранение cookies
            cookies = self.driver.get_cookies()
            if self._save_cookies(cookies):
                self._is_logged_in = True
                logger.info("✅ Авторизация подтверждена и сохранена")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка при подтверждении авторизации: {e}")
            return False

    def refresh_cookies(self):
        """Обновление cookies"""
        try:
            if not self.is_logged_in():
                return False
            
            # Создание временного драйвера для обновления
            temp_driver = self._setup_driver(headless=True)
            if not temp_driver:
                return False
            
            try:
                # Обновление cookies
                temp_driver.get("https://pocketoption.com")
                for cookie in self.driver.get_cookies():
                    temp_driver.add_cookie(cookie)
                temp_driver.refresh()
                
                # Проверка и сохранение
                WebDriverWait(temp_driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "user-avatar"))
                )
                
                new_cookies = temp_driver.get_cookies()
                self._save_cookies(new_cookies)
                logger.info("✅ Cookies успешно обновлены")
                return True
                
            finally:
                temp_driver.quit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении cookies: {e}")
            return False

    def is_logged_in(self):
        """Проверка статуса авторизации"""
        return self._is_logged_in

    def close(self):
        """Закрытие драйвера"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self._is_logged_in = False

    def _get_ssid_from_cookies(self):
        """Получение SSID из cookies и объекта ответа API"""
        try:
            # Сначала пробуем получить из cookies
            cookies = self._load_cookies()
            if not cookies:
                return None
                
            # Ищем SSID в cookies
            for cookie in cookies:
                if cookie.get('name') == 'ssid':
                    return cookie.get('value')
            
            # Если в cookies нет, пробуем получить через API
            if not self.driver:
                logger.error("❌ Драйвер не инициализирован")
                return None
                
            # Получаем SSID из объекта ответа API
            try:
                # Выполняем JavaScript для получения SSID
                ssid = self.driver.execute_script("""
                    return window.localStorage.getItem('ssid') || 
                           window.sessionStorage.getItem('ssid') ||
                           (window.PocketOption && window.PocketOption.ssid);
                """)
                
                if ssid:
                    logger.info("✅ SSID получен из объекта API")
                    return ssid
                    
                # Если не нашли в объекте, пробуем получить из сетевых запросов
                logs = self.driver.get_log('performance')
                for log in logs:
                    if 'ssid' in str(log):
                        try:
                            message = json.loads(log['message'])
                            if 'params' in message and 'response' in message['params']:
                                response = message['params']['response']
                                if 'headers' in response and 'set-cookie' in response['headers']:
                                    cookies = response['headers']['set-cookie']
                                    for cookie in cookies:
                                        if 'ssid=' in cookie:
                                            ssid = cookie.split('ssid=')[1].split(';')[0]
                                            logger.info("✅ SSID получен из сетевых запросов")
                                            return ssid
                        except:
                            continue
                            
            except Exception as e:
                logger.error(f"❌ Ошибка при получении SSID из API: {e}")
            
            logger.error("❌ SSID не найден ни в cookies, ни в API")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка при получении SSID: {e}")
            return None

    def _setup_api_session(self):
        """Настройка сессии для API запросов"""
        try:
            # Получаем SSID
            ssid = self._get_ssid_from_cookies()
            if not ssid:
                logger.error("❌ SSID не найден")
                return False
                
            # Настраиваем сессию
            self._api_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Cookie': f'ssid={ssid}',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://pocketoption.com',
                'Referer': 'https://pocketoption.com/'
            })
            
            self._ssid = ssid
            logger.info("✅ API сессия настроена")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при настройке API сессии: {e}")
            return False

    def check_api_connection(self):
        """Проверка подключения к API"""
        try:
            if not self._ssid:
                if not self._setup_api_session():
                    return False
            
            # Пробуем получить баланс как тестовый запрос
            response = self._api_session.get(f"{self.API_URL}user/balance")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info("✅ Подключение к API успешно")
                    return True
                else:
                    logger.error(f"❌ API вернул ошибку: {data.get('message', 'Неизвестная ошибка')}")
                    return False
            else:
                logger.error(f"❌ Ошибка API: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке API: {e}")
            return False

    def refresh_api_session(self):
        """Обновление API сессии"""
        try:
            # Обновляем cookies
            if not self.refresh_cookies():
                return False
                
            # Пересоздаем API сессию
            return self._setup_api_session()
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении API сессии: {e}")
            return False

    def get_api_session(self):
        """Получение текущей API сессии"""
        if not self._ssid:
            if not self._setup_api_session():
                return None
        return self._api_session 