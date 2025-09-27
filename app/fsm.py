from aiogram.fsm.state import State, StatesGroup

class UserState(StatesGroup):
    VIEWING_STATISTICS = State()

class Verification(StatesGroup):
    """Состояния для процесса верификации пользователя."""
    waiting_for_uid = State()
    waiting_for_verification = State()
    waiting_for_deposit_confirmation = State()

class Trading(StatesGroup):
    """Состояния для процесса получения торговых сигналов."""
    showing_signal_menu = State()
    selecting_market_type = State()
    selecting_pair = State()
    selecting_trading_time = State()
    waiting_for_custom_time = State()
    awaiting_custom_time = State()
    confirming_signal = State()

class AuthStates(StatesGroup):
    """Состояния для процесса авторизации."""
    waiting_for_password = State()
    waiting_for_code = State()
    waiting_for_confirmation = State()

class Admin(StatesGroup):
    """Состояния для админ-панели."""
    admin_menu = State()
    maintenance = State()
    referral_settings = State()
    settings = State()
    settings_referral = State()
    change_referral_link = State()
    change_ref_link_all = State()
    change_ref_link_russia = State()
    change_min_deposit = State()
    change_maintenance_message = State()
    change_welcome_message = State()
    change_finish_message = State()
    change_wallet_address = State()
    view_stats = State()
    send_broadcast = State()
    send_verified_broadcast = State()
    confirm_broadcast = State()
    add_admin = State()
    remove_admin = State() 
    confirm_manual_auth = State()
    viewing_stats = State()
    waiting_for_new_min_deposit = State()
    waiting_for_message_to_send = State()
    waiting_for_text_to_edit = State()

class Authorization(StatesGroup):
    waiting_for_confirmation = State() 