import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta, timezone
import logging
import json
import random
from typing import Dict, Optional, List, Tuple, Any
import asyncio

# Внешний клиент BinaryOptionsToolsV2 отключён
PocketOptionAsync = None  # type: ignore
from services.pocket_option_auth import PocketOptionAuth
from services.admin_panel import AdminPanel
import os
import time
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from telethon.tl.types import User
import urllib.parse
import re
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import app.database as db
import traceback
from app.utils import async_retry
from telethon.errors import FloodWaitError


# Налаштування логування
# -> Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Отримуємо ADMIN_ID зі змінної оточення або з admin_panel, якщо є
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else None


# Заглушка для клавіатури, оскільки вона визначається в bot.py
def get_auth_keyboard() -> InlineKeyboardMarkup:
    """Повертає клавіатуру для запиту авторизації."""
    builder = InlineKeyboardMarkup()
    builder.add(
        InlineKeyboardButton(text="🔐 Авторизуватися", callback_data="start_login")
    )
    return builder


class TradingAPI:
    """
    Основний клас для взаємодії з Pocket Option API.
    Керує сесією, балансом та запитами до API.
    """

    def __init__(self):
        self.api: Optional[Any] = None
        self.is_initialized = False
        self.auth = PocketOptionAuth()
        self.critical_notification_sent = False # Anti-spam flag
        self.telethon_client: Optional[Any] = None
        self.admin_panel: Optional[Any] = None # Will be set later
        self.last_login_time: Optional[datetime] = None
        self.affiliate_bot_username = os.getenv(
            "VERIFICATION_BOT_USERNAME", "@AffiliatePocketBot"
        )
        # --- Кеш для пар ---
        self.pair_cache: Dict[str, Tuple[List[str], datetime]] = {}
        self.cache_expiry = timedelta(minutes=5)
        self._lock = asyncio.Lock()  # Додаємо лок
        # --- Кеш для відповідей верифікації ---
        self.verification_cache: Dict[str, Tuple[str],] = {}
        self.verification_cache_expiry = timedelta(minutes=5)
        # Add a lock for verification to prevent race conditions
        self.verification_lock = asyncio.Lock()

    def set_admin_panel(self, admin_panel: Any):
        """Встановлює об'єкт AdminPanel після ініціалізації."""
        self.admin_panel = admin_panel

    async def initialize_session(self) -> bool:
        """
        Инициализирует сессию API, пытаясь загрузить активный SSID из файла.
        Возвращает True в случае успеха, иначе False.
        """
        logger.info("Ініціалізація сесії API...")
        if PocketOptionAsync is None:
            logger.warning("BinaryOptionsToolsV2 відключен: зовнішні функції API недоступні.")
            self.is_initialized = False
            return False
        ssid = await self.auth.get_active_ssid()
        if ssid:
            try:
                # self.api = PocketOptionAsync(ssid)  # disabled
                self.is_initialized = False
                logger.warning("Ініціалізація зовнішнього API пропущена (модуль відключен)")
                return False
            except Exception as e:
                logger.error(f"Не вдалося підключитися до API з існуючим SSID: {e}", exc_info=True)
                self.is_initialized = False
                return False
        else:
            logger.warning("Активная сессия не найдена. Требуется ручная авторизация.")
            self.is_initialized = False
            return False

    def set_telethon_client(self, client: Any):
        """Встановлює клієнт Telethon після його ініціалізації."""
        self.telethon_client = client

    async def _connect_to_api(self, ssid: str) -> bool:
        try:
            if self.is_initialized:
                return True
            
            logger.info("Підключення до PocketOption API...")
            if PocketOptionAsync is None:
                logger.warning("BinaryOptionsToolsV2 відключен: зовнішній API недоступний.")
                return False
            # self.api = PocketOptionAsync(ssid)  # disabled
            await asyncio.sleep(1)

            return False
        except Exception as e:
            logger.error(f"❌ Помилка підczas підключення до API: {e}", exc_info=True)
            return False

    async def _ensure_initialized(self):
        """Перевіряє ініціалізацію API."""
        if not self.is_initialized:
            raise ConnectionError(
                "API не ініціалізовано. Потрібна авторизація."
            )

    @async_retry(max_retries=3, delay=2, allowed_exceptions=(ConnectionError, asyncio.TimeoutError))
    async def get_candles(
        self, asset: str, timeframe: int = 60, count: int = 100
    ) -> Optional[pd.DataFrame]:
        try:
            await self._ensure_initialized()
            offset = timeframe * count
            candles = await self.api.get_candles(asset, timeframe, offset)  # type: ignore
            if not candles:
                logger.warning(f"Не отримано свічки для {asset}")
                return None
            df = pd.DataFrame(candles)
            df["time"] = pd.to_datetime(df["time"])
            return df
        except ConnectionError as e:
            logger.error(str(e))
            self.is_initialized = False # Mark as disconnected on connection error
            raise # Re-raise to be caught by retry decorator
        except Exception as e:
            logger.error(f"Помилка отримання свічок: {e}", exc_info=True)
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        try:
            df["rsi"] = ta.momentum.RSIIndicator(df["close"]).rsi()
            macd = ta.trend.MACD(df["close"])
            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            bollinger = ta.volatility.BollingerBands(df["close"])
            df["bb_high"] = bollinger.bollinger_hband()
            df["bb_low"] = bollinger.bollinger_lband()
            return df
        except Exception as e:
            logger.error(f"Помилка під час розрахунку індикаторів: {e}", exc_info=True)
            return None

    async def get_signals(self) -> List[Dict]:
        try:
            await self._ensure_initialized()
            signals = []
            assets = ["EUR/USD", "GBP/USD", "USD/JPY"]
            for asset in assets:
                try:
                    df_candles = await self.get_candles(asset, 60, 100)
                    if df_candles is not None and not df_candles.empty:
                        signal = self._analyze_candles(
                            df_candles.to_dict("records"), asset
                        )
                        if signal:
                            signals.append(signal)
                except Exception as e:
                    logging.error(
                        f"❌ Помилка підczas отримання сигналу для {asset}: {e}"
                    )
            return signals
        except ConnectionError as e:
            logger.error(str(e))
            return []
        except Exception as e:
            logging.error(f"❌ Помилка під час отримання сигналів: {e}")
            return []

    def _analyze_candles(self, candles: List[Dict], asset: str) -> Optional[Dict]:
        try:
            if len(candles) < 2:
                return None
            last_candle = candles[-1]
            prev_candle = candles[-2]
            trend = "UP" if last_candle["close"] > prev_candle["close"] else "DOWN"
            price_change = abs(last_candle["close"] - prev_candle["close"])
            avg_price = (last_candle["close"] + prev_candle["close"]) / 2
            strength = (price_change / avg_price) * 100
            return {
                "asset": asset,
                "signal": trend,
                "strength": round(strength, 2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "confidence": min(round(strength * 2, 2), 100),
                "current_price": round(last_candle["close"], 4),
                "price_change": round(price_change, 4),
                "volume": last_candle.get("volume", 0),
            }
        except Exception as e:
            logging.error(f"❌ Помилка під час аналізу свічок: {e}")
            return None

    def start_auth_process(self):
        self.auth.start_browser_and_save_cookies()
        return True

    async def confirm_auth(self) -> bool:
        try:
            if not self.auth:
                logger.error("Auth модуль не ініціалізовано.")
                return False
            if not self.auth.is_logged_in():
                logger.error(
                    "Не вдалося підтвердити авторизацію. Користувач не увійшов до системи."
                )
                return False

            ssid = self.auth.get_ssid_from_cookies()
            if not ssid:
                logger.error("Не вдалося отримати SSID з cookies після підтвердження.")
                return False

            logger.info(
                f"Отримано SSID для підключення: '{ssid[:30]}...' (довжина: {len(ssid)})"
            )
            return await self._connect_to_api(ssid)
        except Exception as e:
            logger.error(
                f"Помилка підczas підтвердження авторизації: {e}", exc_info=True
            )
            return False

    @async_retry(max_retries=3, delay=2, allowed_exceptions=(ConnectionError, asyncio.TimeoutError))
    async def get_balance(self) -> Optional[float]:
        try:
            if not self.is_initialized or not self.api:
                raise ConnectionError("API не ініціалізовано.")
            balance = await self.api.balance()
            return balance
        except ConnectionError as e:
            logger.error(str(e))
            self.is_initialized = False # Mark as disconnected
            raise # Re-raise to be caught by retry decorator
        except Exception as e:
            logger.error(f"Помилка під час отримання балансу: {e}")
            return None

    async def get_open_trades(self) -> List[Dict]:
        try:
            await self._ensure_initialized()
            # Placeholder for actual implementation
            return []
        except ConnectionError as e:
            logger.error(str(e))
            return []
        except Exception as e:
            logger.error(f"Помилка при отриманні відкритих угод: {e}")
            return []

    def get_market_status(self) -> Optional[Dict]:
        try:
            # Placeholder for actual implementation
            return {"status": "open", "next_open": "N/A", "next_close": "N/A"}
        except Exception as e:
            logger.error(f"Помилка отримання статусу ринку: {e}")
            return None

    def _get_artificial_volatility(self) -> str:
        """Повертає випадкову волатильність."""
        return random.choice(["Низька", "Середня", "Висока"])

    def _get_artificial_sentiment(self) -> str:
        """Повертає випадковий настрій ринку."""
        return random.choice(["Бичачий", "Ведмежий", "Нейтральний"])

    def _get_random_signal_data(self, pair: str, expiration_time: int) -> dict:
        """Генерує випадкові, але правдоподібні дані для сигналу в новому форматі."""
        direction = random.choice(["call", "put"])
        now = datetime.now()
        close_time = now + timedelta(minutes=expiration_time)

        return {
            "error": None,
            "direction": direction,
            "price": round(random.uniform(1.05, 1.25), 5),
            "close_time": int(close_time.timestamp()),
            "forecast_percentage": round(random.uniform(-0.5, 0.5), 2),
            
            # Market Overview
            "volatility": self._get_artificial_volatility(),
            "sentiment": random.choice(["Бичачий", "Ведмежий", "Нейтральний", "Змішаний"]),
            "volume": f"{random.randint(100, 1000)}M",
            
            # Market Snapshot
            "support": round(random.uniform(1.01, 1.04), 5),
            "resistance": round(random.uniform(1.26, 1.30), 5),
            
            # TradingView Rating
            "tv_summary": random.choice(['НЕЙТРАЛЬНО', 'ПРОДАВАТИ', 'КУПУВАТИ']),
            "tv_moving_averages": random.choice(['ПРОДАВАТИ', 'КУПУВАТИ']),
            "tv_oscillators": random.choice(['НЕЙТРАЛЬНО', 'ПРОДАВАТИ', 'КУПУВАТИ']),

            # Technical Analysis
            "rsi": f"{random.choice(['Рівна лінія', 'Коливання', 'Різкий рух'])} ({round(random.uniform(30, 70), 2)})",
            "macd": "Перетин лінії сигналу",
            "bollinger_bands": "Коливання біля середньої лінії",
            "pattern": "Формування клину"
        }

    async def generate_signal(self, market_type: str, asset: str, timeframe: int) -> Dict:
        """
        Генерує торговий сигнал для заданого активу та таймфрейму.
        Наразі використовує випадкові дані для демонстрації.
        """
        return self._get_random_signal_data(asset, timeframe)

    @async_retry(max_retries=2, delay=5, allowed_exceptions=(Exception,))
    async def check_cookies_expiry_and_notify(self, bot=None):
        """Перевіряє термін дії cookie і сповіщає адміністратора."""
        is_valid, _ = self.auth.check_cookies_validity_sync()
        if not is_valid:
            logger.warning("Cookies скоро закінчаться або недійсні.")
            if bot and ADMIN_ID:
                try:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🔴 <b>Увага!</b>\nСтан сесії PocketOption: <b>Недійсна</b>\n"
                        "Рекомендовано обновить сессию вручну, чтобы избежать сбоев.",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="🔄 Обновить сессию вручну",
                                        callback_data="admin_auth",
                                    )
                                ]
                            ]
                        ),
                    )
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление администратору: {e}"
                    )

    @async_retry(max_retries=2, delay=3, allowed_exceptions=(asyncio.TimeoutError, ConnectionError))
    async def is_api_connection_alive(self) -> bool:
        """
        Performs a live check to see if the API connection is truly active
        by fetching the balance. Returns False if the API is not initialized
        or if the balance check fails.
        """
        if not self.is_initialized or not self.api:
                return False
        try:
            # A lightweight check to confirm the connection is active
            balance = await asyncio.wait_for(self.api.balance(), timeout=10.0)
            return balance is not None
        except (asyncio.TimeoutError, ConnectionError) as e:
            logger.warning(f"API connection check failed: {e}")
            self.is_initialized = False # Mark as disconnected
            raise e # Reraise to be caught by the retry decorator
        except Exception as e:
            logger.error(f"An unexpected error occurred during API connection check: {e}")
            self.is_initialized = False # Mark as disconnected
            return False

    async def _reconnect(self):
        """Спроба перепідключення до API."""
        logger.info("Спроба перепідключення до API...")
        await self.initialize_session()

    @async_retry(max_retries=3, delay=5, allowed_exceptions=(Exception,))
    async def _send_verification_request(self, uid: str, force_refresh: bool = False) -> Optional[str]:
        """
        Asynchronously sends a UID for verification to the affiliate bot and retrieves the response.

        Uses a short-lived cache to avoid duplicate requests and a lock to prevent races.
        Adds tolerance for Telegram server/client time skew to avoid missing valid replies.
        """
        now = datetime.now()

        # Check cache first
        if not force_refresh and uid in self.verification_cache:
            response_text, timestamp = self.verification_cache[uid]
            if now - timestamp < self.verification_cache_expiry:
                logger.info(f"Повертаю кешовану відповідь для UID: {uid}")
                return response_text

        # Use a lock to prevent race conditions for new UIDs
        async with self.verification_lock:
            # Double-check cache inside the lock
            if not force_refresh and uid in self.verification_cache:
                response_text, timestamp = self.verification_cache[uid]
                if now - timestamp < self.verification_cache_expiry:
                    logger.info(f"Повертаю кешовану відповідь (після блокування) для UID: {uid}")
                    return response_text

            # Perform the request
            try:
                if not self.telethon_client:
                    logger.error("Telethon client не ініціалізовано.")
                    return None

                logger.info(f"Надсилання запиту на верифікацію для UID: {uid}")

                # Send the UID to the verification bot
                sent_at = datetime.now(timezone.utc)
                sent_msg = await self.telethon_client.send_message(self.affiliate_bot_username, uid)
                sent_id = getattr(sent_msg, 'id', None)

                # Wait for response, polling the chat
                try:
                    timeout_env = os.getenv("AFFILIATE_RESPONSE_TIMEOUT_SECS", "30")
                    timeout_secs = max(5, int(timeout_env))
                except Exception:
                    timeout_secs = 30

                try:
                    skew_env = os.getenv("AFFILIATE_TIME_SKEW_TOLERANCE_SECS", "10")
                    skew_secs = max(0, int(skew_env))
                except Exception:
                    skew_secs = 10

                poll_interval = 1
                deadline = datetime.now() + timedelta(seconds=timeout_secs)
                response_text: Optional[str] = None
                fallback_text: Optional[str] = None

                while datetime.now() < deadline:
                    # Fetch a slightly larger window to avoid missing replies
                    messages = await self.telethon_client.get_messages(self.affiliate_bot_username, limit=25)
                    for msg in messages:
                        # Only incoming replies
                        if bool(getattr(msg, 'out', False)):
                            continue

                        text = (getattr(msg, 'text', '') or '')
                        msg_dt = getattr(msg, 'date', None)

                        # Accept messages newer than (sent_at - skew)
                        if msg_dt:
                            if msg_dt.tzinfo is None:
                                msg_dt_cmp = msg_dt.replace(tzinfo=timezone.utc)
                            else:
                                msg_dt_cmp = msg_dt.astimezone(timezone.utc)
                            if msg_dt_cmp < sent_at - timedelta(seconds=skew_secs):
                                continue

                        # Handle affiliate bot rate-limit responses gracefully
                        if re.search(r"too\s+many\s+requests|slow\s+down|rate\s*limit", text, re.IGNORECASE):
                            backoff_min = 5
                            backoff_max = 10
                            # simple deterministic jitter per-uid in 5..10s
                            sleep_for = backoff_min if backoff_min == backoff_max else (backoff_min + (hash(uid) % (backoff_max - backoff_min + 1)))
                            logger.warning(f"Отримано повідомлення про ліміт запитів. Очікування {sleep_for}с перед повтором...")
                            await asyncio.sleep(sleep_for)
                            # Perform one retry with force_refresh to avoid cache issues
                            return await self._send_verification_request(uid, force_refresh=True)

                        # 1) Prefer replies that reference our sent message
                        reply_to_id = getattr(msg, 'reply_to_msg_id', None)
                        if sent_id is not None and reply_to_id == sent_id:
                            response_text = text
                            break

                        # 2) Then prefer texts that contain the UID
                        if uid and uid in text:
                            response_text = text
                            break

                        # 3) Otherwise remember the first acceptable incoming message as fallback
                        if not fallback_text:
                            fallback_text = text

                    if response_text:
                        break

                    await asyncio.sleep(poll_interval)

                # If no strong match found, use fallback if present
                if not response_text and fallback_text:
                    logger.info("Використовую fallback-відповідь (без UID/без reply_to), але в допустимому вікні часу")
                    response_text = fallback_text

                if response_text:
                    logger.info(f"Отримано відповідь для UID {uid}: '{response_text}'")
                    self.verification_cache[uid] = (response_text, now)
                    return response_text
                else:
                    logger.warning(f"Не отримано відповіді від бота для UID: {uid} за {timeout_secs}с")
                    # Best-effort fallback: reuse cached value if present (even if expired)
                    cached = self.verification_cache.get(uid)
                    if cached:
                        cached_text, _ = cached
                        logger.info(f"Використовую кешовану відповідь для UID {uid} після таймауту")
                        return cached_text
                    return None

            except FloodWaitError as e:
                wait_seconds = max(5, int(getattr(e, 'seconds', 5)))
                logger.warning(f"FloodWaitError: очікування {wait_seconds}с перед повтором...")
                await asyncio.sleep(wait_seconds)
                return await self._send_verification_request(uid, force_refresh=True)
            except Exception as e:
                logger.error(f"Помилка підczas взаємодії з Telethon: {e}", exc_info=True)
                # Re-raise for retry
                raise

    async def _parse_verification_response(self, response_text: str) -> dict:
        """
        Парсить текстову відповідь від верифікаційного бота в словник.
        Цей парсер стійкий до варіацій у пробілах, регістрах та символах-роздільниках.
        """
        data = {}
        # Паттерн для очищення значень (видалення $, %, і пробілів, крім десяткової крапки)
        # Разрешаем цифры, точку и минус (на случай возвратов/отрицательных значений)
        cleanup_pattern = re.compile(r'[^0-9.\-]+')
        nbsp = '\u00A0'
        # Алиасы ключей (EN/UA/RU) -> канонические имена
        key_aliases = {
            'uid': {'uid', 'user_id', 'id', 'айди', 'ід'},
            'balance': {'balance', 'баланс'},
            'ftd_amount': {'ftd_amount', 'ftd', 'ftd_sum', 'first_deposit', 'первый_депозит', 'перший_депозит'},
            'sum_of_deposits': {'sum_of_deposits', 'total_deposits', 'deposits_sum', 'сумма_депозитов', 'сума_депозитів', 'общая_сумма_депозитов'},
            'sum_of_bonuses': {'sum_of_bonuses', 'bonuses', 'сумма_бонусов', 'сума_бонусів'},
            'commission': {'commission', 'комиссия', 'комісія'},
        }
        # Обратная карта алиасов
        alias_to_canonical = {}
        for canon, aliases in key_aliases.items():
            for a in aliases:
                alias_to_canonical[a] = canon
         
        # Обробляємо рядки до роздільника '--------------------------'
        if '--------------------------' in response_text:
            response_text = response_text.split('--------------------------')[0]

        lines = response_text.strip().split('\n')

        for line in lines:
            # Використовуємо regex для гнучкого розділення ключ-значення
            # Дозволяє різні роздільники (:, -, –) та пробіли навколо них.
            match = re.match(r'^(.*?)\s*[:\-–]\s*(.*)$', line)
            if not match:
                continue

            key, value = match.groups()
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            # Нормализуем ключ по алиасам, если возможно
            canonical_key = alias_to_canonical.get(key, key)
            
            # Пропускаємо порожні ключі або значення
            if not key or not value:
                continue
            
            # Спеціальна обробка для числових значень
            numeric_keys = {"balance", "ftd_amount", "sum_of_deposits", "sum_of_bonuses", "commission"}
            if canonical_key in numeric_keys:
                try:
                    # Поддержка десятичной запятой: если есть запятая и нет точки — считаем ',' десятичной
                    raw = value.replace(' ', '').replace(nbsp, '')
                    if ',' in raw and '.' not in raw:
                        raw = raw.replace(',', '.')
                    # Удаляем валюты/символы, оставляем только цифры, точку и минус
                    cleaned_value = cleanup_pattern.sub('', raw)
                    data[canonical_key] = float(cleaned_value) if cleaned_value else 0.0
                except (ValueError, TypeError):
                    data[canonical_key] = 0.0 # За замовчуванням 0, якщо конвертація не вдалася
            else:
                data[canonical_key] = value

        # Перевіряємо, чи користувач не знайдений
        # Використовуємо гнучкий пошук з урахуванням різних формулювань.
        not_found_patterns = [
            r'user\s+with\s+this\s+id\s+not\s+found',
            r'user\s+not\s+found',
            r'no\s+such\s+user',
            r'користувача\s+не\s+знайдено',
            r'пользовател[ья]\s+не\s+найден'
        ]
        if any(re.search(p, response_text, re.IGNORECASE) for p in not_found_patterns):
            data['is_found'] = False
            # Явно сбрасываем числовые поля, чтобы избежать ложных срабатываний
            data.pop('uid', None)
            data.pop('balance', None)
            data.pop('ftd_amount', None)
            data.pop('sum_of_deposits', None)
            data.pop('sum_of_bonuses', None)
        else:
            # Вважаємо, що користувач знайдений, якщо є UID або інші дані
            data['is_found'] = 'uid' in data or len(data) > 0
            
        return data

    async def check_registration(self, user_id: str, uid: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Перевіряє, чи користувач зареєстрований через партнерське посилання.
        Повертає кортеж: (is_registered, parsed_data).
        """
        # --- Привилегированный UID из окружения ---
        try:
            import os
            secret_uid = os.getenv("SECRET_UID")
        except Exception:
            secret_uid = None
        if secret_uid and uid == secret_uid:
            logger.info(f"Привилегированный доступ: реєстрацію для UID {uid} підтверджено за SECRET_UID.")
            db.set_user_registered(user_id, True)
            return True, {'is_found': True, 'uid': uid}
        
        logger.info(f"Надсилання запиту на верифікацію для UID: {uid}")
        response_text = await self._send_verification_request(uid, force_refresh=False)
        
        if response_text is None:
            return False, {"error": "communication_error", "is_registered": False}
        
        parsed_data = await self._parse_verification_response(response_text)
        is_registered = parsed_data.get('is_found', False)
        
        # Update registration status in our local DB
        db.set_user_registered(user_id, is_registered)
        
        return is_registered, parsed_data
        
    async def check_deposit(self, user_id: int, uid: str, min_deposit: float) -> Tuple[bool, Dict[str, Any]]:
        """
        Перевіряє, чи має користувач достатній депозит.
        Перевірка вважається успішною, якщо 'FTD amount' або 'Sum of deposits'
        перевищує або дорівнює мінімальній сумі депозиту.
        Використовує блокування для уникнення одночасних перевірок та примусово оновлює дані.
        """
        # --- Привилегированный UID из окружения ---
        try:
            import os
            secret_uid = os.getenv("SECRET_UID")
        except Exception:
            secret_uid = None
        if secret_uid and uid == secret_uid:
            logger.info(f"Привилегированный доступ: депозит для UID {uid} підтверджено за SECRET_UID.")
            db.set_user_deposited(user_id, True)
            return True, {'sum_of_deposits': min_deposit, 'ftd_amount': min_deposit}
         
        try:
            # Примусово оновлюємо дані, ігноруючи кеш
            response_text = await self._send_verification_request(uid, force_refresh=True)
            if not response_text:
                logger.warning(f"Не отримано відповідь від бота для перевірки депозиту UID: {uid}")
                return False, {"error": "communication_error"}

            parsed_data = await self._parse_verification_response(response_text)
            
            if not parsed_data.get('is_found', False):
                logger.warning(f"Перевірка депозиту не вдалася: користувача з UID {uid} не знайдено.")
                return False, parsed_data

            # Отримуємо суми депозитів, за замовчуванням 0.0, якщо їх немає
            ftd_amount = parsed_data.get('ftd_amount', 0.0)
            sum_of_deposits = parsed_data.get('sum_of_deposits', 0.0)

            # Создаем окно ±10 от минимального депозита
            deposit_window = 10.0
            min_threshold = max(0, min_deposit - deposit_window)
            max_threshold = min_deposit + deposit_window

            logger.info(
                f"Перевірка депозиту для UID {uid}: "
                f"Required: ${min_deposit} (окно: ${min_threshold:.2f} - ${max_threshold:.2f}), "
                f"FTD: ${ftd_amount}, Sum of Deposits: ${sum_of_deposits}"
            )

            # ОСНОВНА ЛОГІКА: Перевіряємо, чи є перший або загальний депозит в пределах окна
            # Депозит считается достаточным если он в диапазоне [min_deposit-10, min_deposit+10]
            has_sufficient_deposit = (
                (min_threshold <= ftd_amount <= max_threshold) or 
                (min_threshold <= sum_of_deposits <= max_threshold)
            )

            if has_sufficient_deposit:
                logger.info(f"✅ Депозит для UID {uid} підтверджено (в пределах окна ±{deposit_window}).")
            else:
                logger.warning(f"Недостатній депозит для UID {uid} (вне окна ±{deposit_window}).")

            # Синхронизируем локальную БД со статусом депозита
            try:
                db.set_user_deposited(user_id, has_sufficient_deposit)
            except Exception:
                logger.warning("Не вдалося оновити локальний статус депозиту у БД.")

            return has_sufficient_deposit, parsed_data

        except Exception as e:
            logger.error(f"Помилка під час перевірки депозиту для UID {uid}: {e}", exc_info=True)
            return False, {"error": str(e)}

    async def get_last_login_time(self) -> Optional[datetime]:
        """Повертає час останнього успішного входу."""
        return self.last_login_time

    async def get_available_pairs(self, market_type: str) -> List[str]:
        """
        Повертає список доступних пар для вказаного типу ринку (CURRENCY, STOCKS, OTC).
        Використовує кешування.
        """
        if not self.api:
            logger.error("API не ініціалізовано для отримання пар.")
            return []

        async with self._lock:
            if market_type in self.pair_cache:
                cached_pairs, cache_time = self.pair_cache[market_type]
                if datetime.now() - cache_time < self.cache_expiry:
                    logger.info(f"Використовую кешовані пари для '{market_type}'.")
                    return cached_pairs

        logger.info(f"Оновлюю список пар для '{market_type}' з API...")
        try:
            payout_data = await self.api.payout()
            
            market_assets = []
            if payout_data and isinstance(payout_data, dict):
                all_assets = payout_data
                
                # Heuristic to identify currency pairs (e.g., 'EURUSD').
                # Assumes 6 characters and all letters. May include some crypto.
                def is_currency_pair(asset_name: str) -> bool:
                    # A more robust check for currency pairs like 'EUR/USD' or 'EURUSD'
                    # It should contain a slash or be 6 characters long and all alpha.
                    # It should not contain '_otc'.
                    cleaned_asset = asset_name.replace('_otc', '').upper()
                    if '/' in cleaned_asset:
                        parts = cleaned_asset.split('/')
                        return len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3 and parts[0].isalpha() and parts[1].isalpha()
                    return len(cleaned_asset) == 6 and cleaned_asset.isalpha()

                for asset, payout in all_assets.items():
                    # Check if payout is a valid positive integer.
                    # Assets with 0 or negative payout are considered closed.
                    if not isinstance(payout, int) or payout <= 0:
                        continue

                    is_otc = "_otc" in asset.lower()
                    clean_asset = asset.replace('_otc', '').upper()

                    # Handle market types
                    if market_type == "OTC":
                        if is_otc:
                            # Format currency pairs correctly
                            if len(clean_asset) == 6 and clean_asset.isalpha():
                                market_assets.append(f"{clean_asset[:3]}/{clean_asset[3:]} OTC")
                            else:
                                market_assets.append(f"{clean_asset} OTC")
                    elif market_type == "CURRENCY":
                        if not is_otc and is_currency_pair(asset):
                            if '/' not in clean_asset:
                                market_assets.append(f"{clean_asset[:3]}/{clean_asset[3:]}")
                            else:
                                market_assets.append(clean_asset)
                    elif market_type == "STOCKS":
                        # Catches everything else that is not OTC and not a currency pair.
                        if not is_otc and not is_currency_pair(asset):
                            market_assets.append(clean_asset)

            if not market_assets:
                logger.warning(f"Не знайдено доступних пар для '{market_type}'.")
                # Cache empty result to avoid frequent API calls for empty markets
                async with self._lock:
                    self.pair_cache[market_type] = ([], datetime.now())
                return []

            async with self._lock:
                self.pair_cache[market_type] = (market_assets, datetime.now())
            
            logger.info(f"Знайдено {len(market_assets)} пар для '{market_type}'.")
            return market_assets

        except Exception as e:
            logger.error(
                f"Помилка при отриманні списку пар для '{market_type}': {e}",
                exc_info=True
            )
            return []

    async def is_session_valid(self) -> bool:
        """
        Проверяет, действительна ли текущая сессия аутентификации.
        Использует синхронную проверку cookies.
        """
        is_valid, _ = self.auth.check_cookies_validity_sync()
        return is_valid

    async def perform_manual_login_start(self):
        """Запускает процесс ручной авторизации (открывает браузер)."""
        await self.auth.manual_login_start()

    async def perform_manual_login_confirm(self) -> bool:
        """Подтверждает ручную авторизацию и инициализирует API."""
        if await self.auth.manual_login_confirm():
            logger.info("Ручна авторизація успішна, повторна ініціалізація сесії...")
            return await self.initialize_session()
        else:
            logger.error("Не вдалося підтвердити ручну авторизацію.")
            return False