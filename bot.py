import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

# Загрузка переменных окружения и настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# Импорт основных компонентов после настройки
from app.dispatcher import dp, bot, admin_panel, telethon_client, trading_api # trading_api включен
from app.background import setup_background_tasks
from app.middleware import MaintenanceMiddleware, AdminCheckMiddleware
import handlers.user_handlers    
import handlers.admin_panel_handlers
# import auth_handlers

async def main():
    """Основная функция для запуска бота"""
    # 1. Инициализация Telethon клиента
    await telethon_client.initialize()

    # 2. Инициализация сессии TradingAPI (только для проверки рефералов)
    trading_api.set_telethon_client(telethon_client)
    await trading_api.initialize_session()
    
    # 3. Регистрация middleware
    dp.update.middleware(MaintenanceMiddleware())
    handlers.admin_panel_handlers.admin_router.message.middleware(AdminCheckMiddleware())
    handlers.admin_panel_handlers.admin_router.callback_query.middleware(AdminCheckMiddleware())
    
    # 4. Настройка и запуск фоновых задач
    await setup_background_tasks(dp)
    
    # Роутеры уже зарегистрированы в dispatcher.py, здесь их регистрировать не нужно.
    logger.info("Роутеры успешно зарегистрированы в диспетчере.")

    # 5. Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Запуск поллинга...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"An error occurred during polling: {e}")
    finally:
        # Корректное завершение работы
        logger.info("Бот останавливается...")
        
        # Остановка асинхронных задач - ОТКЛЮЧЕНО
        # auth_task.cancel()

        # Отключение Telethon клиента
        if telethon_client.is_connected():
            await telethon_client.disconnect()
        
        # Сохранение данных админ-панели
        logger.info("Сохранение данных...")
        admin_panel._save_data()
        
        # Закрытие Selenium WebDriver - ОТКЛЮЧЕНО
        # if trading_api and trading_api.auth and trading_api.auth.driver:
        #     logger.info("Закрытие Selenium WebDriver...")
        #     trading_api.auth._close_driver()
        
        # Закрытие сессии бота
        await bot.session.close()
        logger.info("Бот был успешно остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал на завершение работы.")