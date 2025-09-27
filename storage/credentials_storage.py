import json
import os
from typing import Dict, Optional, Tuple

from .db_store import get_credentials as storage_get_credentials, set_credentials as storage_set_credentials


def save_credentials(user_id, email, password, uid):
    """Saves or updates user credentials including UID in the unified storage."""
    data = storage_get_credentials()
    if not isinstance(data, dict):
        data = {}
    data[str(user_id)] = {
        'email': email,
        'password': password,
        'uid': uid
    }
    storage_set_credentials(data)


def load_credentials(user_id: int) -> Optional[Tuple[str, str, Optional[str]]]:
    """Loads user credentials (email, password, UID) from unified storage."""
    data = load_all_credentials()
    user_data = data.get(str(user_id))
    if user_data:
        return user_data.get("email"), user_data.get("password"), user_data.get("uid")
    return None, None, None


def load_all_credentials() -> Dict:
    """Loads all credentials from the unified storage."""
    data = storage_get_credentials()
    return data if isinstance(data, dict) else {}


def delete_credentials(user_id: int):
    """Deletes credentials for a specific user in the unified storage."""
    data = storage_get_credentials()
    if not isinstance(data, dict):
        data = {}
    if str(user_id) in data:
        del data[str(user_id)]
        storage_set_credentials(data)


def get_credentials(user_id: int) -> dict:
    """Retrieves credentials for a given user from unified storage."""
    user_id_str = str(user_id)
    data = storage_get_credentials()
    return data.get(user_id_str, {}) 