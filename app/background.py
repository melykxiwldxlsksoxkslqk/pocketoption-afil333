import asyncio
import logging
from datetime import datetime, timedelta
# Avoid circular imports: import dispatcher objects lazily inside functions where needed
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import logging
from services.boost_service import update_all_boosts, check_and_notify_active_boosts
from services.statistics_service import stats_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

# Пороги для проверки
SESSION_CHECK_INTERVAL_OK = 1800  # 30 минут, если все в порядке
SESSION_CHECK_INTERVAL_ERROR = 3600  # 1 час, если сессия умерла (чтобы не спамить)
PROACTIVE_REFRESH_THRESHOLD_HOURS = 12  # За сколько часов до истечения пытаться обновить

async def periodic_auth_check(bot, trading_api, admin_panel, interval_seconds: int = 3600):
    """
    Periodically checks the API connection status and warns the admin if the session
    is invalid, expired, or expiring soon. Runs once per hour.
    """
    await asyncio.sleep(20) # Initial delay to allow the bot to start up
    logger.info("🚀 Запущено періодичну перевірку статусу сесії.")

    while True:
        try:
            admin_id = admin_panel.get_admin_id()
            if not admin_id:
                await asyncio.sleep(interval_seconds)
                continue

            # Check 1: Is connection dead or session expired? (Critical)
            if not await trading_api.is_api_connection_alive():
                # Anti-spam check: only send if a notification hasn't been sent already.
                if not trading_api.critical_notification_sent:
                    logger.warning("Перевірка показала, що сесія API недійсна. Надсилаю сповіщення.")
                    auth_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔑 Оновити сесію", callback_data="start_manual_auth")]
                    ])
                    await bot.send_message(
                        admin_id,
                        "🔴 <b>Критична помилка запуску!</b>\n\nСесія API недійсна або відсутня. Бот не може отримувати ринкові дані.\n\nНатисніть кнопку нижче, щоб розпочати процес авторизації.",
                        reply_markup=auth_keyboard,
                        parse_mode="HTML"
                    )
                    trading_api.critical_notification_sent = True # Set flag after sending
            else:
                # If the connection is alive, reset the flag so it can notify again if it fails later.
                if trading_api.critical_notification_sent:
                    logger.info("З'єднання з API відновлено. Скидаю прапорець сповіщення.")
                    trading_api.critical_notification_sent = False
                
                # Check 2: Is session expiring soon? (Warning)
                expiry_warning = trading_api.auth.get_expiry_warning(days_threshold=3)
                if expiry_warning:
                    logger.info(f"Сесія скоро закінчується: {expiry_warning}")
                    auth_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔑 Оновити сесію", callback_data="start_manual_auth")]
                    ])
                    await bot.send_message(
                        admin_id,
                        f"🟡 <b>Попередження: термін дії сесії скоро закінчиться</b>\n\n{expiry_warning} Щоб уникнути збоїв у роботі, рекомендується оновити її.",
                        reply_markup=auth_keyboard,
                        parse_mode="HTML"
                    )
                else:
                    logger.info("Перевірка сесії: все гаразд, з'єднання активне.")

        except Exception as e:
            logger.error(f"Помилка під час періодичної перевірки сесії: {e}", exc_info=True)
            
        await asyncio.sleep(interval_seconds)


async def main():
    scheduler = AsyncIOScheduler()
    from app.dispatcher import bot
    scheduler.add_job(update_all_boosts, 'interval', minutes = 30, args=[bot])
    scheduler.start()
    print("Scheduler started...")
    while True:
        await asyncio.sleep(1)


async def update_statistics_periodically():
    """Periodically updates the statistics for dummy accounts."""
    while True:
        await stats_service.update_balances()
        await asyncio.sleep(10) # Check every 10 seconds

async def boost_notification_scheduler():
    """Periodically checks and notifies users about their active boost balance."""
    logging.info("🚀 Boost notification scheduler started.")
    while True:
        try:
            from app.dispatcher import bot
            await check_and_notify_active_boosts(bot)
        except Exception as e:
            logging.error(f"Error in boost_notification_scheduler: {e}", exc_info=True)
        await asyncio.sleep(1600) # Check every 1600 seconds to hit exact per-user hour marks

async def setup_background_tasks(dp):
    logging.info("Starting background tasks...")
    asyncio.create_task(main())
    asyncio.create_task(update_statistics_periodically())
    asyncio.create_task(boost_notification_scheduler())