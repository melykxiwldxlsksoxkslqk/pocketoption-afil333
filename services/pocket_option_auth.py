import os
import time
import json
import traceback
import urllib.parse
import re
import asyncio
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from app.utils import logger


# --- Environment Detection ---
IS_HEROKU = 'DYNO' in os.environ

# --- Constants ---
COOKIES_FILE = "pocket_option_cookies.json"
COOKIES_EXPIRY_FILE = "cookies_expiry.json"
LOGIN_URL = "https://pocketoption.com/en/login/"

class PocketOptionAuth:
    """
    Handles all authentication logic for PocketOption, including manual
    login via Selenium and session management via cookie files.
    This class provides a clean, unified interface for authentication.
    """
    def __init__(self, cookies_file=COOKIES_FILE, expiry_file=COOKIES_EXPIRY_FILE):
        self.cookies_file = cookies_file
        self.expiry_file = expiry_file
        self.driver: Optional[webdriver.Chrome] = None

    async def _setup_driver(self) -> bool:
        """
        Sets up the Selenium WebDriver, adapting to the execution environment.
        Returns True on success, False on failure.
        """
        if self.driver:
            return True
        try:
            logger.info("Setting up WebDriver...")
            chrome_options = Options()
            # Common options for stability and to avoid detection
            chrome_options.add_argument("--window-size=1280,800")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--log-level=3") # Suppress console noise
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option("useAutomationExtension", False)

            if IS_HEROKU:
                logger.info("Heroku environment detected. Configuring for headless mode.")
                chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")
                service = Service(executable_path=os.environ.get("CHROMEDRIVER_PATH"))
                chrome_options.add_argument("--headless=new")
            else:
                logger.info("Local environment detected. Using Selenium's automatic WebDriver manager.")
                # By creating a Service() object without an executable_path,
                # Selenium will automatically download and manage the correct driver version.
                service = Service()
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(60)
            logger.info("✅ WebDriver initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize WebDriver: {e}\n{traceback.format_exc()}")
            return False

    def _save_session(self, cookies: List[Dict]):
        """Saves cookies and their real expiry time to files (JSON)."""
        session_cookie = next((c for c in cookies if c.get("name") == "ci_session"), None)
        
        if session_cookie and session_cookie.get("expiry"):
             expiry_time = datetime.fromtimestamp(session_cookie.get("expiry"))
             logger.info(f"Session expiry found from 'ci_session': {expiry_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            # Fallback if no expiry is found in the session cookie
            expiry_time = datetime.now() + timedelta(days=7)
            logger.warning("Could not find 'ci_session' expiry. Using default 7-day expiry.")
        
        # Log the full cookies for debugging
        logger.info(f"--- Full cookies being saved ---")
        logger.info(json.dumps(cookies, indent=2))
        logger.info(f"---------------------------------")
        
        with open(self.cookies_file, "w", encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)
        with open(self.expiry_file, "w", encoding='utf-8') as f:
            json.dump({"expiry": expiry_time.isoformat()}, f)
        logger.info(f"✅ Session (cookies and expiry) saved successfully.")

    def _close_driver(self):
        """Safely quits the WebDriver if it's running."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Ignoring error while closing WebDriver: {e}")
            finally:
                self.driver = None

    # --- Public API for Authentication ---

    async def get_active_ssid(self) -> Optional[str]:
        """
        The primary method to get a valid SSID.
        It reads the session from local files, checks expiry, and constructs the SSID.
        Returns a valid SSID string or None if the session is invalid or missing.
        """
        logger.info("Attempting to load session from file...")
        
        # 1. Check if session files exist and are not expired
        expiry_time = self.get_expiration_time()
        if not expiry_time:
            logger.info("No valid expiry file found. Manual login required.")
            return None
        
        if datetime.now() >= expiry_time:
            logger.warning("Session has expired. Manual login required.")
            return None
        
        # 2. Load cookies and construct SSID
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # --- Logic to build SSID from cookies ---
            session_val = None
            uid_val = None
            is_demo = 0
            autologin_cookie_found = False

            for cookie in cookies:
                name = cookie.get("name")
                value = cookie.get("value")

                if name == "ci_session":
                    session_val = urllib.parse.unquote(value)
                elif name == "autologin":
                    autologin_cookie_found = True
                    autologin_val = urllib.parse.unquote(value)
                    match = re.search(r'"user_id";(?:s:\d+:"|i:)(\d+)', autologin_val)
                    if match:
                        try:
                            uid_val = int(match.group(1))
                        except (ValueError, TypeError):
                            logger.warning(f"Found user_id but failed to parse as integer: {match.group(1)}")
                    else:
                        logger.warning(f"Regex failed to find user_id in autologin cookie. Raw value: {autologin_val}")
                elif name == "platform_type" and value == "1":
                    is_demo = 1
            
            if session_val and uid_val is not None:
                auth_payload = {"session": session_val, "isDemo": is_demo, "uid": uid_val, "platform": 1}
                ssid = f'42["auth",{json.dumps(auth_payload)}]'
                logger.info("✅ Active session SSID constructed successfully from file.")
                return ssid
            else:
                if not session_val: 
                    logger.error("Crucial 'ci_session' cookie not found in the saved session file.")
                if not autologin_cookie_found:
                    logger.error("Crucial 'autologin' cookie not found. This is often caused by not checking 'Remember Me' during login.")
                elif uid_val is None: # This case means autologin was found but parsing failed
                    logger.error("Found 'autologin' cookie, but failed to extract 'user_id' from it. The cookie format may have changed.")
                
                logger.warning("Could not construct SSID. Manual authorization required.")
                return None

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not load or parse cookie file: {e}. Manual login required.")
            return None

    async def manual_login_start(self):
        """
        STEP 1: Starts the manual login process by opening a browser.
        """
        self._close_driver() # Ensure any old driver is closed
        logger.info("Starting manual authorization...")
        
        if not await self._setup_driver():
            logger.error("Failed to start browser for manual login.")
            return

        try:
            self.driver.get(LOGIN_URL)
            logger.info("="*60)
            logger.info("Browser opened. Please log in manually in the Selenium window.")
            logger.info("IMPORTANT: Make sure to check the 'Remember Me' checkbox to save your session.")
            logger.info("="*60)
        except Exception as e:
            logger.error(f"Failed to open login page: {e}")
            self._close_driver()

    async def manual_login_confirm(self) -> bool:
        """
        STEP 2: Confirms the manual login, saves the new session, and closes the browser.
        Returns True on success, False on failure.
        """
        if not self.driver:
            logger.error("Confirmation failed: Browser driver not found.")
            return False

        try:
            logger.info("Confirming authorization status...")
            # Wait for a reliable element that indicates a successful login
            WebDriverWait(self.driver, 45).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-avatar"))
            )
            logger.info("✅ User avatar found, login confirmed.")
            
            # Get fresh cookies and save the session
            cookies = self.driver.get_cookies()
            self._save_session(cookies)
            return True
        except TimeoutException:
            logger.error("Login confirmation failed: Timed out waiting for user avatar. Please try again.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during login confirmation: {e}")
            return False
        finally:
            self._close_driver()

    def are_cookies_valid(self) -> bool:
        """
        Checks if the session cookies exist and have not expired.
        Returns True if cookies are present and not expired, False otherwise.
        """
        expiry_time = self.get_expiration_time()
        if not expiry_time:
            return False
        # Return True if the current time is before the expiry time
        return datetime.now() < expiry_time

    def get_expiration_time(self) -> Optional[datetime]:
        """Reads the expiry time from the dedicated expiry file."""
        if not os.path.exists(self.expiry_file):
            return None
        try:
            with open(self.expiry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return datetime.fromisoformat(data['expiry'])
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
			
    def get_expiry_warning(self, days_threshold: int = 3) -> Optional[str]:
        """
        Checks if the session is expiring soon and returns a warning message.
        """
        expiry_time = self.get_expiration_time()
        if not expiry_time:
            return "Сесія не знайдена або недійсна."
        
        if datetime.now() >= expiry_time:
            return "Термін дії сесії закінчився."
            
        days_left = (expiry_time - datetime.now()).days
        if days_left <= days_threshold:
            return f"⚠️ Увага! Термін дії сесії закінчується через {days_left} дн."
        
        return None # No warning needed 

    async def start_browser_and_save_cookies(self):
        """Helper method to run the full manual login flow."""
        await self.manual_login_start()
        # This just opens the browser. Confirmation and saving is separate.

    def is_logged_in(self) -> bool:
        """Simple check based on cookie validity."""
        return self.are_cookies_valid()

    async def get_ssid_from_cookies(self) -> Optional[str]:
        """Alias for get_active_ssid to match the new trading_api."""
        return await self.get_active_ssid()
        
    def check_cookies_validity_sync(self) -> Tuple[bool, Optional[datetime]]:
        """
        Synchronous check of cookie validity.
        Returns a tuple: (is_valid, expiry_time).
        """
        expiry_time = self.get_expiration_time()
        if not expiry_time:
            return False, None
        is_valid = datetime.now() < expiry_time
        return is_valid, expiry_time 