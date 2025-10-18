from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# URLs for external links
ABOUT_US_URL = "https://teletype.in/@trdrocketua/DN_LSR6eWNw"
FAQ_URL = "https://teletype.in/@trdrocketua/2IiklQY1uiX"
TELEGRAM_URL = "https://t.me/+bWIZFj7N9RJlYmYy"
RU_ABOUT_URL = "https://teletype.in/@traderocketai/SHZeFeUrOvf"
RU_FAQ_URL = "https://teletype.in/@traderocketai/_R5PWCs2tkS"


def get_language_select_keyboard():
    """Keyboard to choose language at start."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="choose_lang_uk")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="choose_lang_ru")]
    ])
    return keyboard


def get_start_keyboard(lang: str = "uk"):
    """Returns the main menu keyboard."""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Выбрать платформу", callback_data="choose_platform")],
            [
                InlineKeyboardButton(text="О нас", url=RU_ABOUT_URL),
                InlineKeyboardButton(text="Вопрос/Ответ", url=RU_FAQ_URL)
            ],
            [
                InlineKeyboardButton(text="Наш телеграм", url=TELEGRAM_URL)
            ],
            [InlineKeyboardButton(text="ТОП Аккаунты", callback_data="stats_irl")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обрати платформу", callback_data="choose_platform")],
        [
            InlineKeyboardButton(text="Про нас", url=ABOUT_US_URL),
            InlineKeyboardButton(text="Питання/Відповідь", url=FAQ_URL)
        ],
        [
            InlineKeyboardButton(text="Наш телеграм", url=TELEGRAM_URL)
        ],
        [InlineKeyboardButton(text="ТОП Акаунти", callback_data="stats_irl")]
    ])
    return keyboard


def get_statistics_keyboard(lang: str = "uk"):
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Обновить", callback_data="update_statistics")],
            [InlineKeyboardButton(text="Назад", callback_data="start_menu")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оновити", callback_data="update_statistics")],
        [InlineKeyboardButton(text="Назад", callback_data="start_menu")]
    ])
    return keyboard


def get_platform_select_keyboard(lang: str = "uk"):
    """Returns the platform selection keyboard."""
    if lang == "ru":
        buttons = [
            [
                InlineKeyboardButton(text="Pocket Option", callback_data="platform_pocket"),
                InlineKeyboardButton(text="BINANCE", callback_data="platform_binance")
            ],
            [InlineKeyboardButton(text="Назад", callback_data="start_menu")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [
            InlineKeyboardButton(text="Pocket Option", callback_data="platform_pocket"),
            InlineKeyboardButton(text="BINANCE", callback_data="platform_binance")
        ],
        [InlineKeyboardButton(text="Назад", callback_data="start_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_binance_bybit_keyboard(manager_url: str, lang: str = "uk"):
    """Returns keyboard for Binance/Bybit flow with a manager link."""
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pocket_option_prereg_keyboard(lang: str = "uk"):
    """Keyboard after user sees registration instructions."""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Аккаунт зарегистрировал!", callback_data="pocket_option_verify")],
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акаунт зареєстрував!", callback_data="pocket_option_verify")],
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ])
    return keyboard


def get_pocket_option_retry_keyboard(lang: str = "uk"):
    """Keyboard for when verification fails, allows retrying."""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Аккаунт зарегистрировал!", callback_data="pocket_option_verify")],
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Акаунт зареєстрував!", callback_data="pocket_option_verify")],
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ])
    return keyboard


def get_funded_keyboard(lang: str = "uk"):
    """Keyboard for when user needs to select if they have funded their account"""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Депозит пополнен!", callback_data="pocket_option_funded")],
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Депозит поповнено!", callback_data="pocket_option_funded")],
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ])
    return keyboard


def get_pocket_option_start_boost_keyboard(lang: str = "uk"):
    """Returns keyboard for starting the boost after connection."""
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton(text="Начать разгон", callback_data="start_boost")],
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [InlineKeyboardButton(text="Почати розгін", callback_data="start_boost")],
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_boost_active_keyboard(lang: str = "uk"):
    """Returns keyboard for when the boost is active."""
    if lang == "ru":
        buttons = [
            [
                InlineKeyboardButton(text="Остановить разгон", callback_data="stop_boost"),
                InlineKeyboardButton(text="Текущий баланс", callback_data="current_balance")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [
            InlineKeyboardButton(text="Зупинити розгін", callback_data="stop_boost"),
            InlineKeyboardButton(text="Поточний баланс", callback_data="current_balance")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_boost_finished_keyboard(lang: str = "uk"):
    """Keyboard for when a boost session has finished."""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать разгон", callback_data="start_paid_boost")],
            [InlineKeyboardButton(text="Меню", callback_data="choose_platform")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Почати розгін", callback_data="start_paid_boost")],
        [InlineKeyboardButton(text="Меню", callback_data="choose_platform")]
    ])
    return keyboard


def get_paid_boost_keyboard(manager_url: str, lang: str = "uk"):
    """Keyboard for the paid boost message with external manager link."""
    if lang == "ru":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Я оплатил", url=manager_url)],
            [InlineKeyboardButton(text="Меню", callback_data="choose_platform")]
        ])
        return keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатив", url=manager_url)],
        [InlineKeyboardButton(text="Меню", callback_data="choose_platform")]
    ])
    return keyboard


def get_back_to_platform_select_keyboard(lang: str = "uk"):
    """Returns a simple 'BACK' button to the platform selection menu."""
    if lang == "ru":
        buttons = [
            [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="choose_platform")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Admin Keyboards ---

def get_admin_auth_keyboard(lang: str = "uk"):
    """Кнопка для ручної авторизації адміна."""
    if lang == "ru":
        buttons = [[InlineKeyboardButton(text="Авторизоваться", callback_data="start_manual_auth")]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [[InlineKeyboardButton(text="Авторизуватися", callback_data="start_manual_auth")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_auth_confirmation_keyboard(lang: str = "uk"):
    """Возвращает клавиатуру для подтверждения ручной авторизации."""
    if lang == "ru":
        buttons = [[InlineKeyboardButton(text="✅ Я вошёл в аккаунт", callback_data="confirm_auth")]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [[InlineKeyboardButton(text="✅ Я увійшов в акаунт", callback_data="confirm_auth")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_panel_keyboard(lang: str = "uk"):
    """Возвращает клавиатуру с кнопкой 'Назад в админ-панель'."""
    if lang == "ru":
        buttons = [[InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [[InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_referral_settings_keyboard(settings: dict, lang: str = "uk"):
    """Створює клавіатуру для налаштувань реферальної програми."""
    min_deposit = settings.get('min_deposit', 20)
    if lang == "ru":
        buttons = [
            [
                InlineKeyboardButton(text=f"💰 Депозит: ${min_deposit}", callback_data="admin_change_min_deposit")
            ],
            [
                InlineKeyboardButton(text="🔗 Изменить ссылку", callback_data="admin_change_ref_link")
            ],
            [InlineKeyboardButton(text="⬅️ Назад к настройкам", callback_data="admin_settings")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [
        [
            InlineKeyboardButton(text=f"💰 Депозит: ${min_deposit}", callback_data="admin_change_min_deposit")
        ],
        [
            InlineKeyboardButton(text="🔗 Змінити посилання", callback_data="admin_change_ref_link")
        ],
        [InlineKeyboardButton(text="⬅️ Назад до налаштувань", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard(back_callback: str, lang: str = "uk"):
    """Універсальна кнопка 'Назад'."""
    if lang == "ru":
        buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
    return InlineKeyboardMarkup(inline_keyboard=buttons) 