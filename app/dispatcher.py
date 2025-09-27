import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from services.admin_panel import AdminPanel
from services.trading_api import TradingAPI
from .telethon_code import TelethonClient
from handlers.user_handlers import user_router
from handlers.admin_panel_handlers import admin_router
# from auth_handlers import router as auth_router

# Загружаем переменные окружения из .env файла
load_dotenv()

# --- Загрузка и проверка обязательных переменных окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле. Пожалуйста, добавьте его.")
if not ADMIN_IDS_RAW:
    raise ValueError("ADMIN_IDS не найден в .env файле. Пожалуйста, добавьте его.")

try:
    # Преобразуем строку ID администраторов в список целых чисел
    admin_ids_list = [int(id) for id in ADMIN_IDS_RAW.split(',') if id.strip()]
except ValueError:
    raise ValueError("ADMIN_IDS должен быть списком чисел, разделенных запятыми (например, 123,456).")

# --- Инициализация компонентов ---

# Инициализация бота и диспетчера
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Инициализация панели администратора
admin_panel = AdminPanel(admin_ids=admin_ids_list)

# Инициализация Trading API - ВРЕМЕННО ОТКЛЮЧЕНО
trading_api = TradingAPI()
telethon_client = TelethonClient(session_name='telethon.session', api_id=int(os.getenv('TELEGRAM_API_ID')), api_hash=os.getenv('TELEGRAM_API_HASH'))

async def on_startup(dispatcher):
    """Function to run on startup."""
    # await telethon_client.start() # This is handled in bot.py now
    trading_api.set_telethon_client(telethon_client)
    await trading_api.initialize_session()

async def on_shutdown(dispatcher):
    """Function to run on shutdown."""
    await telethon_client.disconnect()

# Регистрация роутеров
dp.include_router(user_router)
dp.include_router(admin_router)
# dp.include_router(auth_router)

# Регистрация функций startup и shutdown - ВРЕМЕННО ОТКЛЮЧЕНО
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)