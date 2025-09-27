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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
    else:
        # For regular messages, we edit the message itself
        chat_id = message.chat.id
        message_id = message.message_id
        original_message_to_delete = message.message_id if not edit else None


    photo_path = os.path.join('images', photo_name)
    if not os.path.exists(photo_path):
        logger.error(f"Photo not found at {photo_path}")
        # Fallback to a text message
        if edit:
            await message.bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        return

    cached_file_id = admin_panel.get_file_id(photo_name)
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

        if not cached_file_id and sent_message.photo:
            admin_panel.set_file_id(photo_name, sent_message.photo[-1].file_id)
        
        return sent_message

    except TelegramBadRequest as e:
        logger.error(f"Could not send or edit photo message: {e}")
        # Fallback to sending a new text message if editing/sending photo fails
        try:
            if edit:
                await message.bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                 # To avoid duplicate messages, let's just log the error if initial send fails
                 logger.error("Initial photo send failed, not sending fallback text to avoid duplicates.")
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
    """Calculates the remaining time and returns it as a formatted string."""
    now = datetime.now()
    remaining = end_time - now
    if remaining.total_seconds() <= 0:
        return "0d 0h 0m"
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{days}d {hours}h {minutes}m"