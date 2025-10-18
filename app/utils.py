from aiogram.types import Message, BufferedInputFile, InputMediaPhoto, FSInputFile
from aiogram.exceptions import TelegramBadRequest
import random
from datetime import datetime, timedelta
import locale
import asyncio
import logging
import os
import pytz
from functools import wraps
from aiogram.types import FSInputFile
from aiogram import types # Import the types module
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load optional images rename map once
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_IMAGES_MAP_PATH = os.path.join(_PROJECT_ROOT, 'images_map.json')
try:
    with open(_IMAGES_MAP_PATH, 'r', encoding='utf-8') as _f:
        _IMAGES_RENAME_MAP = json.load(_f)
        # normalize keys to lowercase for case-insensitive lookup
        _IMAGES_RENAME_MAP = {str(k).lower(): str(v) for k, v in _IMAGES_RENAME_MAP.items()}
except Exception:
    _IMAGES_RENAME_MAP = {}


def _apply_image_alias(photo_name: str) -> str:
    """Apply alias/rename map for image filenames (case-insensitive)."""
    if not photo_name:
        return photo_name
    mapped = _IMAGES_RENAME_MAP.get(photo_name.lower())
    return mapped or photo_name


def _resolve_image_path(photo_name: str, lang: str | None = None) -> str | None:
    """Try to find the image by name relative to project root regardless of CWD.
    If lang == 'ru' and RU-variant exists (e.g. "1 (2).jpg"), prefer it.
    Returns absolute path or None if not found."""
    # Apply mapping first
    effective_name = _apply_image_alias(photo_name)

    # Build name variants with language preference
    names_to_try = []
    if lang and lang.lower() == 'ru':
        root, ext = os.path.splitext(effective_name)
        if ext:
            ru_variant = f"{root} (2){ext}"
            names_to_try.append(ru_variant)
    names_to_try.append(effective_name)

    # app/utils.py -> project root = parent of app
    project_root = _PROJECT_ROOT

    # Search candidates deterministically
    for name in names_to_try:
        candidates = [
            os.path.join(project_root, 'images', name),
            os.path.join(os.getcwd(), 'images', name)
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

    # Case-insensitive lookup inside known images folders
    for folder in {os.path.join(project_root, 'images'), os.path.join(os.getcwd(), 'images')}:
        if os.path.isdir(folder):
            try:
                lower_targets = [n.lower() for n in names_to_try]
                for fname in os.listdir(folder):
                    f_lower = fname.lower()
                    if f_lower in lower_targets:
                        return os.path.join(folder, fname)
            except Exception:
                pass
    return None

async def send_message_with_photo(message: Message, photo_name: str, text: str, reply_markup=None, parse_mode="HTML", edit=False):
    """
    Sends or edits a message to include a photo, using cached file_id if available.
    If edit is True, it will try to edit the provided message.
    Otherwise, it deletes the previous message to keep the chat clean.
    """
    from app.dispatcher import admin_panel # Import admin_panel for caching (lazy)
    
    # Determine the chat_id and if the original message can be deleted
    is_callback = isinstance(message, types.CallbackQuery)
    if is_callback:
        # For callbacks, we edit the message the button was on
        chat_id = message.message.chat.id
        message_id = message.message.message_id
        original_message_to_delete = message.message.message_id if not edit else None
        user_id = message.from_user.id
    else:
        # For regular messages, we edit the message itself
        # Guard if message is None (e.g., previous call failed and returned None)
        if message is None:
            logger.error("send_message_with_photo called with message=None")
            return None
        chat_id = message.chat.id
        message_id = getattr(message, 'message_id', None)
        original_message_to_delete = message.message_id if not edit else None
        user_id = message.from_user.id if hasattr(message, 'from_user') else None

    # Resolve user's language for image variant and caching
    user_lang = 'uk'
    try:
        profile = admin_panel.get_user(user_id) or {}
        l = (profile.get('lang') or 'uk').lower()
        user_lang = 'ru' if l == 'ru' else 'uk'
    except Exception:
        pass

    # If we're editing and the new text/caption is identical to existing, skip API call
    if edit:
        try:
            if is_callback:
                current_text = message.message.caption or message.message.text or ""
            else:
                current_text = getattr(message, 'caption', None) or getattr(message, 'text', None) or ""
            if isinstance(text, str) and current_text.strip() == text.strip():
                if is_callback:
                    try:
                        await message.answer()
                    except Exception:
                        pass
                    return message.message
                return message
        except Exception:
            # If introspection fails, proceed normally
            pass

    photo_path = _resolve_image_path(photo_name, user_lang)
    if not photo_path:
        logger.error(f"Photo not found: {photo_name}")
        # Fallback to a text message and RETURN the message so callers can reuse it
        if edit and message_id is not None:
            try:
                # Try edit caption first (if the message is media)
                try:
                    return await message.bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=message_id,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                except TelegramBadRequest as e:
                    msg = str(e).lower()
                    if "message is not modified" in msg:
                        return message
                    # If no caption to edit, try editing text
                    return await message.bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
            except Exception as e:
                logger.warning(f"Edit text fallback failed: {e}. Sending new message")
        return await message.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

    cache_key = f"{photo_name}__{user_lang}"
    cached_file_id = admin_panel.get_file_id(cache_key)
    photo_input = cached_file_id if cached_file_id else FSInputFile(photo_path)
    media = InputMediaPhoto(media=photo_input, caption=text, parse_mode=parse_mode)

    try:
        if edit:
            sent_message = await message.bot.edit_message_media(
                media=media,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            )
        else:
            if original_message_to_delete:
                try:
                    await message.bot.delete_message(chat_id, original_message_to_delete)
                except TelegramBadRequest as e:
                    # Suppress harmless "message to delete not found" noise
                    if "message to delete not found" in str(e).lower():
                        pass
                    else:
                        logger.warning(f"Could not delete message {original_message_to_delete}: {e}")
            
            sent_message = await message.bot.send_photo(
                chat_id=chat_id,
                photo=photo_input,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

        if not cached_file_id and getattr(sent_message, 'photo', None):
            admin_panel.set_file_id(cache_key, sent_message.photo[-1].file_id)
        
        return sent_message

    except TelegramBadRequest as e:
        # Treat "message is not modified" as a benign no-op
        if "message is not modified" in str(e).lower():
            return message
        logger.error(f"Could not send or edit photo message: {e}")
        # Fallback to sending a new text message if editing/sending photo fails
        try:
            if edit and message_id is not None:
                err = str(e).lower()
                if "message is not modified" in err:
                    return message
                # Try edit caption (for media messages)
                try:
                    return await message.bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=message_id,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
                except TelegramBadRequest as e2:
                    if "message is not modified" in str(e2).lower():
                        return message
                    # Fallback to editing text if caption edit is not applicable
                    return await message.bot.edit_message_text(
                        text=text,
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
            else:
                # To avoid duplicate messages, let's just send a single fallback text
                return await message.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as fallback_e:
            logger.error(f"Fallback text message also failed: {fallback_e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in send_message_with_photo: {e}")

    return None


def async_retry(max_retries=3, delay=2, allowed_exceptions=()):
    """
    A decorator to retry an async function if it fails.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except allowed_exceptions as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__} due to allowed exception: {e}. Retrying...")
                    if attempt + 1 == max_retries:
                        raise  # Re-raise the last exception
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__} with an unexpected exception: {e}",
                        exc_info=True
                    )
                    # For unexpected errors, we might not want to retry, so we re-raise immediately.
                    # Or, to be safe, we can continue retrying. For now, let's re-raise.
                    raise
            # This part should not be reachable if max_retries > 0
            return None
        return wrapper
    return decorator

async def check_api_initialized(message: Message) -> bool:
    """Перевірка ініціалізації API"""
    from app.dispatcher import trading_api
    if not trading_api.is_initialized:
        await message.answer("⏳ Ініціалізація API...")
        success = await trading_api.confirm_auth()
        if not success:
            await message.answer("❌ Помилка ініціалізації API. Спробуйте пізніше.")
            return False
    return True 

async def _send_text_message(
    message: Message,
    text: str,
    reply_markup: object = None,
    edit: bool = False,
    parse_mode: str = "HTML"
):
    """
    Sends a text message instead of a photo.
    If edit is True, it tries to edit the existing message.
    If editing fails, it deletes the old message and sends a new one.
    """
    try:
        if edit and hasattr(message, 'message_id'):
            # First, try to delete the message this interaction came from.
            await message.delete()
        
        # Now, send a new message.
        # Use message.chat.id because the original message might be gone.
        return await message.bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except TelegramBadRequest as e:
        if "message to delete not found" in str(e).lower():
            # benign
            return await message.answer(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        logger.warning(f"Could not edit or delete message, sending a new one. Error: {e}")
    except Exception as e:
        logger.error(f"Failed to send text message: {e}")

    # Fallback to just sending a new message if any of the above fails
    try:
        return await message.answer(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception:
        return None

def _format_asset_name(asset: str) -> str:
    """Форматує технічну назву активу в читабельний вигляд."""
    name_upper = asset.upper()
    is_otc = name_upper.endswith('_OTC')
    
    # Видаляємо суфікс _OTC для базової обробки
    clean_name = name_upper.removesuffix('_OTC')

    # Перевіряємо, чи це стандартна валютна пара (6 літер)
    if len(clean_name) == 6 and clean_name.isalpha():
        formatted_pair = f"{clean_name[:3]}/{clean_name[3:]}"
        if is_otc:
            return f"{formatted_pair} OTC"
        return formatted_pair
    
    # Для інших випадків (акції, індекси тощо) повертаємо назву як є,
    # але додаємо ' OTC' якщо потрібно
    if is_otc:
        return f"{clean_name} OTC"
    return clean_name

def get_remaining_time_str(end_time: datetime) -> str:
    """Calculates the remaining time and returns it as a formatted string (UA)."""
    now = datetime.now()
    remaining = end_time - now
    if remaining.total_seconds() <= 0:
        return "0д 0г 0хв"
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{days}д {hours}г {minutes}хв"