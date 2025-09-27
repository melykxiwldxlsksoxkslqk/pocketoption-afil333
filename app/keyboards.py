from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# URLs for external links
ABOUT_US_URL = "https://teletype.in/@boostmydepoteam/qeECUsujIo1"
FAQ_URL = "https://teletype.in/@boostmydepoteam/stqAm06JXE5"
TELEGRAM_URL = "https://t.me/+xAjquQ5_gIwxZGQy"

def get_start_keyboard():
    """Returns the main menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Choose Platform", callback_data="choose_platform")],
        [
            InlineKeyboardButton(text="ABOUT US", url=ABOUT_US_URL),
            InlineKeyboardButton(text="FAQ", url=FAQ_URL)
        ],
        [
            InlineKeyboardButton(text="Telegram Channel", url=TELEGRAM_URL)
        ],
        [InlineKeyboardButton(text="Statistics Irl", callback_data="stats_irl")]
    ])
    return keyboard

def get_statistics_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Update", callback_data="update_statistics")],
        [InlineKeyboardButton(text="Back", callback_data="start_menu")]
    ])
    return keyboard

def get_platform_select_keyboard():
    """Returns the platform selection keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="BINANCE", callback_data="platform_binance"),
            InlineKeyboardButton(text="BYBIT", callback_data="platform_bybit")
        ],
        [InlineKeyboardButton(text="Pocket Option", callback_data="platform_pocket")],
        [InlineKeyboardButton(text="BACK", callback_data="start_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_binance_bybit_keyboard(manager_url: str):
    """Returns keyboard for Binance/Bybit flow with a manager link."""
    buttons = [
        [InlineKeyboardButton(text="Contact Manager", url=manager_url)],
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_pocket_option_prereg_keyboard():
    """Keyboard after user sees registration instructions."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="I have registered my account", callback_data="pocket_option_verify")],
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ])
    return keyboard

def get_pocket_option_retry_keyboard():
    """Keyboard for when verification fails, allows retrying."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="I have registered my account", callback_data="pocket_option_verify")],
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ])
    return keyboard

def get_funded_keyboard():
    """Keyboard for when user needs to select if they have funded their account"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="I have funded my account", callback_data="pocket_option_funded")],
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ])
    return keyboard

def get_pocket_option_start_boost_keyboard():
    """Returns keyboard for starting the boost after connection."""
    buttons = [
        [InlineKeyboardButton(text="Start Boost", callback_data="start_boost")],
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_boost_active_keyboard():
    """Returns keyboard for when the boost is active."""
    buttons = [
        [
            InlineKeyboardButton(text="Stop Boost", callback_data="stop_boost"),
            InlineKeyboardButton(text="Current Balance", callback_data="current_balance")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_boost_finished_keyboard():
    """Keyboard for when a boost session has finished."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start Boost", callback_data="start_paid_boost")],
        [InlineKeyboardButton(text="Menu", callback_data="choose_platform")]
    ])
    return keyboard

def get_paid_boost_keyboard():
    """Keyboard for the paid boost message."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="I've Paid", callback_data="paid_boost_confirmed")],
        [InlineKeyboardButton(text="Menu", callback_data="choose_platform")]
    ])
    return keyboard

def get_back_to_platform_select_keyboard():
    """Returns a simple 'BACK' button to the platform selection menu."""
    buttons = [
        [InlineKeyboardButton(text="BACK", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Admin Keyboards ---

def get_admin_auth_keyboard():
    """Кнопка для ручної авторизації адміна."""
    buttons = [[InlineKeyboardButton(text="Авторизуватися", callback_data="start_manual_auth")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_auth_confirmation_keyboard():
    """Возвращает клавиатуру для подтверждения ручной авторизации."""
    buttons = [[InlineKeyboardButton(text="✅ Я увійшов в акаунт", callback_data="confirm_auth")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_to_panel_keyboard():
    """Возвращает клавиатуру с кнопкой 'Назад в админ-панель'."""
    buttons = [[InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_referral_settings_keyboard(settings: dict):
    """Створює клавіатуру для налаштувань реферальної програми."""
    min_deposit = settings.get('min_deposit', 20)
    buttons = [
        [
            InlineKeyboardButton(text=f"💰 Депозит: ${min_deposit}", callback_data="admin_change_min_deposit")
        ],
        [
            InlineKeyboardButton(text="🔗 Змінити посилання (Світ)", callback_data="admin_change_ref_link_all"),
            InlineKeyboardButton(text="🔗 Змінити посилання (РФ)", callback_data="admin_change_ref_link_russia")
        ],
        [InlineKeyboardButton(text="⬅️ Назад до налаштувань", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard(back_callback: str):
    """Універсальна кнопка 'Назад'."""
    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
    return InlineKeyboardMarkup(inline_keyboard=buttons) 