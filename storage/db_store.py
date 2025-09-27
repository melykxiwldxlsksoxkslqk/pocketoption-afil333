import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

DB_FILE = 'users.db'  # reuse existing DB name so it's easy to find

_LOCK = threading.Lock()


@contextmanager
def _conn_cursor():
    conn = sqlite3.connect(DB_FILE)
    try:
        # Performance PRAGMAs (safe for single-writer usage)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-20000;")  # ~20MB cache
        conn.execute("PRAGMA busy_timeout=5000;")  # wait up to 5s if locked
        yield conn, conn.cursor()
        conn.commit()
    finally:
        conn.close()


def _init_db():
    with _conn_cursor() as (conn, cur):
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        # Create an index on json keys we frequently read? Not needed for KV.


def _get_raw(key: str) -> Optional[str]:
    with _conn_cursor() as (conn, cur):
        cur.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def _set_raw(key: str, value: str) -> None:
    with _conn_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO kv_store(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_section(section: str, default: Optional[Any] = None) -> Any:
    with _LOCK:
        raw = _get_raw(section)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default


def set_section(section: str, value: Any) -> None:
    with _LOCK:
        _set_raw(section, json.dumps(value, ensure_ascii=False))


def update_section(section: str, updater: Callable[[Any], Any], default: Optional[Any] = None) -> Any:
    with _LOCK:
        current = get_section(section, default)
        updated = updater(current)
        set_section(section, updated)
        return updated


# Convenience wrappers

def get_admin_data(default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    val = get_section('admin', default if default is not None else {})
    return val if isinstance(val, dict) else (default if default is not None else {})


def set_admin_data(admin_data: Dict[str, Any]) -> None:
    set_section('admin', admin_data)


def get_credentials() -> Dict[str, Any]:
    val = get_section('credentials', {})
    return val if isinstance(val, dict) else {}


def set_credentials(creds: Dict[str, Any]) -> None:
    set_section('credentials', creds)


def get_boost_data() -> Dict[str, Any]:
    val = get_section('boost', {})
    return val if isinstance(val, dict) else {}


def set_boost_data(data: Dict[str, Any]) -> None:
    set_section('boost', data)


def get_statistics_accounts() -> list:
    val = get_section('statistics_accounts', [])
    return val if isinstance(val, list) else []


def set_statistics_accounts(accounts: list) -> None:
    set_section('statistics_accounts', accounts)


# Legacy migration

def _read_json_file(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def migrate_legacy_files():
    changed = False

    # Admin
    if not get_section('admin'):
        legacy_admin = _read_json_file('admin_data.json', None)
        if isinstance(legacy_admin, dict) and legacy_admin:
            set_section('admin', legacy_admin)
            changed = True

    # Credentials
    if not get_section('credentials'):
        legacy_creds = _read_json_file('user_credentials.json', {})
        if isinstance(legacy_creds, dict) and legacy_creds:
            set_section('credentials', legacy_creds)
            changed = True

    # Boost data
    if not get_section('boost'):
        legacy_boost = _read_json_file('boost_data.json', {})
        if isinstance(legacy_boost, dict) and legacy_boost:
            set_section('boost', legacy_boost)
            changed = True

    # Statistics accounts
    if not get_section('statistics_accounts'):
        legacy_accounts = _read_json_file('dummy_accounts.json', [])
        if isinstance(legacy_accounts, list) and legacy_accounts:
            set_section('statistics_accounts', legacy_accounts)
            changed = True

    return changed


def integrity_ok() -> bool:
    """Runs PRAGMA integrity_check and returns True if DB is OK.
    Use for quick health checks when diagnosing issues.
    """
    try:
        with _conn_cursor() as (conn, cur):
            cur.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            return bool(row and row[0] == 'ok')
    except Exception:
        return False


# Initialize on import
_init_db()
migrate_legacy_files() 