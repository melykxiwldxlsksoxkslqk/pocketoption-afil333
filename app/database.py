import logging
from typing import Optional, Dict, Any
import sqlite3

DB_FILE = 'users.db'

logger = logging.getLogger(__name__)


def create_or_update_user(user_id: int, username: Optional[str] = None):
    """Створює або оновлює користувача в 'базі даних'."""
    from app.dispatcher import admin_panel
    admin_panel.add_or_update_user(user_id, username=username)


def set_user_registered(user_id: int, is_registered: bool):
    """Встановлює статус реєстрації користувача."""
    from app.dispatcher import admin_panel
    admin_panel.update_user_field(user_id, "is_registered", is_registered)


def set_user_deposited(user_id: int, has_deposit: bool):
    """Встановлює статус депозиту користувача."""
    from app.dispatcher import admin_panel
    admin_panel.update_user_field(user_id, "has_deposit", has_deposit)


def set_user_uid(user_id: int, uid: str):
    """Встановлює PocketOption UID для користувача."""
    from app.dispatcher import admin_panel
    admin_panel.update_user_field(user_id, "uid", uid)


def is_fully_verified(user_id: int) -> bool:
    """Перевіряє, чи є користувач повністю верифікованим."""
    from services.boost_service import get_user_boost_info  # Import locally
    boost_info = get_user_boost_info(user_id)
    return boost_info is not None


def get_user_uid(user_id: int) -> Optional[str]:
    """Отримує PocketOption UID користувача."""
    from app.dispatcher import admin_panel
    return admin_panel.get_user_uid(user_id)


def get_all_users() -> Dict[str, Any]:
    """Повертає словник усіх користувачів."""
    from app.dispatcher import admin_panel
    return admin_panel.get_all_users()


def get_user_id_by_uid(uid: str) -> Optional[int]:
    """Отримує Telegram user_id за PocketOption UID."""
    from app.dispatcher import admin_panel
    return admin_panel.get_user_id_by_uid(uid)


def get_user_by_pocket_id(pocket_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE pocket_option_id=?", (pocket_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def has_used_free_boost(user_id: int) -> bool:
    """Checks if the user has already used their free boost."""
    from services.boost_service import get_user_boost_info  # Import locally
    boost_info = get_user_boost_info(user_id)
    return boost_info and boost_info.get('boost_count', 0) > 0


def has_active_boost(user_id: int) -> bool:
    """Check if the user has an active boost session."""
    from services.boost_service import get_user_boost_info  # Import locally
    boost_info = get_user_boost_info(user_id)
    return boost_info and boost_info.get('is_active', False) 