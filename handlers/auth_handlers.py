from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
import logging
import asyncio

from app.dispatcher import trading_api
from app.fsm import Authorization
from app.keyboards import get_auth_confirmation_keyboard

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "start_user_auth")
async def handle_start_user_auth(callback: CallbackQuery, state: FSMContext):
    """
    Handles the 'start_user_auth' button for regular users.
    """
    await callback.message.edit_text(
        "⏳ Запускаю браузер для ручної авторизації...\n\nБудь ласка, зачекайте, це може зайняти до 30 секунд.",
        reply_markup=None
    )
    
    # This runs the browser opening in the background
    asyncio.create_task(trading_api.perform_manual_login_start())
    
    await asyncio.sleep(5) # Give some time for the browser to initialize

    await callback.message.edit_text(
        "🤖 Будь ласка, виконайте вхід в акаунт у вікні браузера, яке відкрилося.\n\nПісля успішного входу та повного завантаження торгової кімнати, натисніть кнопку нижче.",
        reply_markup=get_auth_confirmation_keyboard() # This keyboard should contain 'confirm_auth'
    )
    await state.set_state(Authorization.waiting_for_confirmation)

@router.callback_query(F.data == "confirm_auth", StateFilter(Authorization.waiting_for_confirmation))
async def handle_confirm_auth(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Handles the confirmation from the user that they have logged in.
    """
    await callback.message.edit_text("⏳ Перевіряю авторизацію та зберігаю сесію...", reply_markup=None)
    
    # This runs the confirmation logic
    success = await trading_api.perform_manual_login_confirm()
    
    if success:
        trading_api.critical_notification_sent = False # Reset anti-spam flag
        balance = await trading_api.get_balance()
        balance_text = f"${balance:.2f}" if balance is not None else "не вдалося отримати"
        await callback.message.edit_text(
            f"✅ Авторизація пройшла успішно! Сесію збережено.\n\n"
            f"Поточний баланс: <b>{balance_text}</b>",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await callback.message.edit_text(
            "❌ Не вдалося підтвердити авторизацію. Будь ласка, спробуйте ще раз:\n\n1. Переконайтесь, що ви увійшли в акаунт.\n2. Оновіть сторінку (F5) у браузері.\n3. Натисніть кнопку підтвердження ще раз.",
            reply_markup=get_auth_confirmation_keyboard()
    )
    await callback.answer()