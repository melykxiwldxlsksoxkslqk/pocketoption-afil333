from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from datetime import datetime, timedelta
import random
import logging

# Assuming keyboards and message_templates are correctly set up
# This is a simplified approach. In a real app, you'd use a more robust way
# to get keyboards and messages, avoiding direct dependencies if possible.
from app.keyboards import get_boost_finished_keyboard, get_boost_active_keyboard
from config.message_templates import load_messages
from app.utils import get_remaining_time_str
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest
from storage.db_store import get_boost_data as storage_get_boost_data, set_boost_data as storage_set_boost_data
# Avoid circular import by importing admin_panel lazily where needed


def get_boost_data():
    # Read from unified storage
    data = storage_get_boost_data()
    return data if isinstance(data, dict) else {}


def save_boost_data(data):
    # Write to unified storage
    if not isinstance(data, dict):
        data = {}
    storage_set_boost_data(data)


def update_balance_on_demand(user_id: int):
    """
    Calculates the new balance based on the time passed since the last update.
    This is called on-demand when the user requests their balance.
    """
    data = get_boost_data()
    user_id_str = str(user_id)
    now = datetime.now()

    if user_id_str not in data or not data[user_id_str].get('is_active'):
        return data.get(user_id_str)

    boost_info = data[user_id_str]
    last_update = datetime.fromisoformat(boost_info['last_update'])
    end_time = datetime.fromisoformat(boost_info['end_time'])

    # Calculations should not go past the boost's end time
    effective_time = min(now, end_time)
    
    time_since_last_update = effective_time - last_update
    # Change interval to 3600 seconds (1 hour)
    intervals_passed = int(time_since_last_update.total_seconds() // 3600)

    if intervals_passed > 0:
        current_balance = boost_info['current_balance']
        start_balance = boost_info['start_balance']

        # Apply an increase for each interval that has passed
        for _ in range(intervals_passed):
            # Calculate the increase as 12-15% of the current balance for compounding effect
            increase_percentage = random.uniform(0.12, 0.15)
            increase_amount = current_balance * increase_percentage
            current_balance += increase_amount
        
        boost_info['current_balance'] = current_balance
        # We only advance the 'last_update' time by the intervals we've processed
        boost_info['last_update'] = (last_update + timedelta(seconds=intervals_passed * 3600)).isoformat()
        
        save_boost_data(data)
        
    return boost_info

def start_boost(user_id: int, initial_balance: float, platform: str):
    """Starts a new boost session for a user."""
    data = get_boost_data()
    user_id_str = str(user_id)
    
    now = datetime.now()
    end_time = now + timedelta(hours=24) # Boost duration

    data[user_id_str] = {
        'user_id': user_id,
        'is_active': True,
        'start_time': now.isoformat(),
        'end_time': end_time.isoformat(),
        'last_update': now.isoformat(),
        'last_notified': now.isoformat(),
        'start_balance': initial_balance,
        'current_balance': initial_balance,
        'final_balance': None,
        'boost_count': data.get(user_id_str, {}).get('boost_count', 0) + 1,
        'platform': platform
    }
    save_boost_data(data)

def stop_boost(user_id: int):
    data = get_boost_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        # Perform a final balance calculation before stopping
        final_info = update_balance_on_demand(user_id)
        
        # Re-read data as it might have been modified
        data = get_boost_data()
        if user_id_str in data:
            data[user_id_str]['is_active'] = False
            if final_info:
                data[user_id_str]['final_balance'] = final_info['current_balance']
            save_boost_data(data)


async def update_all_boosts(bot: Bot):
    """
    Background task that runs periodically to check for expired boosts.
    The balance update is now handled on-demand.
    """
    data = get_boost_data()
    now = datetime.now()
    messages = load_messages()
    
    expired_user_ids = []
    for user_id_str, boost_info in data.items():
        if boost_info.get('is_active'):
            end_time = datetime.fromisoformat(boost_info['end_time'])
            if now >= end_time:
                expired_user_ids.append(int(user_id_str))

    for user_id in expired_user_ids:
        # Perform one final calculation to get the balance up to the expiration time
        final_info = update_balance_on_demand(user_id)
        
        # Now mark as inactive and save final balance
        current_data = get_boost_data()
        user_id_str = str(user_id)

        if user_id_str in current_data and current_data[user_id_str].get('is_active'):
            current_data[user_id_str]['is_active'] = False
            current_data[user_id_str]['final_balance'] = final_info['current_balance']
            save_boost_data(current_data)

            # Send boost finished message
            try:
                final_message = messages['pocket_option_boost_finished'].format(
                    initial_balance=f"${final_info['start_balance']:.2f}",
                    final_balance=f"${final_info['current_balance']:.2f}"
                )
                await bot.send_message(
                    user_id,
                    final_message,
                    reply_markup=get_boost_finished_keyboard()
                )
            except Exception as e:
                print(f"Failed to send boost finished message to {user_id_str}: {e}")

def get_user_boost_info(user_id: int):
    data = get_boost_data()
    return data.get(str(user_id))

async def check_and_notify_active_boosts(bot: Bot):
    """
    Checks active boosts, updates their balance if an interval has passed,
    and notifies the user.
    """
    data_before_update = get_boost_data()
    messages = load_messages()
    active_boosts = [info for info in data_before_update.values() if info.get('is_active')]
    logging.info(f"Checking {len(active_boosts)} active boosts for notifications...")

    for boost_info in active_boosts:
        user_id_str = str(boost_info['user_id'])
        user_id = int(user_id_str)
        original_balance = boost_info.get('current_balance')

        # This function calculates, updates, and saves the new balance
        update_balance_on_demand(user_id)
        
        # Re-fetch data to check if we should notify by time
        data_after_update = get_boost_data()
        boost_info_after_update = data_after_update.get(user_id_str)
        
        if not boost_info_after_update:
            logging.warning(f"Could not find boost info for user {user_id_str} after update.")
            continue

        new_balance = boost_info_after_update.get('current_balance')
        logging.info(f"User {user_id_str}: Original Balance=${original_balance}, New Balance=${new_balance}")

        # Notify strictly once per hour since last_notified
        last_notified_iso = boost_info_after_update.get('last_notified')
        try:
            last_notified_dt = datetime.fromisoformat(last_notified_iso) if last_notified_iso else None
        except Exception:
            last_notified_dt = None
        now_dt = datetime.now()
        # Only notify if at least one hour passed AND balance actually changed
        elapsed_ok = last_notified_dt is None or (now_dt - last_notified_dt).total_seconds() >= 3600
        balance_changed = (original_balance is None) or (abs(float(new_balance) - float(original_balance)) > 1e-6)
        should_notify = elapsed_ok and balance_changed

        if should_notify:
            logging.info(f"Time-based notify for user {user_id_str}.")
            try:
                end_time = datetime.fromisoformat(boost_info_after_update['end_time'])
                remaining_time_str = get_remaining_time_str(end_time)
                    
                balance_message = messages["pocket_option_current_balance"].format(
                    current_balance=f"${new_balance:.2f}",
                    remaining_time=remaining_time_str
                )
                    
                # Resolve image path robustly from project root
                photo_name = "your currency balance.jpg"
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                candidates = [
                    os.path.join(project_root, 'images', photo_name),
                    os.path.join(os.getcwd(), 'images', photo_name),
                ]
                photo_path = None
                for p in candidates:
                    if os.path.exists(p):
                        photo_path = p
                        break
                if not photo_path:
                    # case-insensitive scan
                    for folder in {os.path.join(project_root, 'images'), os.path.join(os.getcwd(), 'images')}:
                        if os.path.isdir(folder):
                            lower_target = photo_name.lower()
                            try:
                                for fname in os.listdir(folder):
                                    if fname.lower() == lower_target:
                                        photo_path = os.path.join(folder, fname)
                                        break
                            except Exception:
                                pass
                        if photo_path:
                            break

                # Lazy import to avoid circular dependency at module import time
                from app.dispatcher import admin_panel
                cached_file_id = admin_panel.get_file_id(photo_name)
                photo_input = cached_file_id if cached_file_id else (FSInputFile(photo_path) if photo_path else None)

                if photo_input is not None:
                    sent_message = await bot.send_photo(
                        chat_id=user_id,
                        photo=photo_input,
                        caption=balance_message,
                        reply_markup=get_boost_active_keyboard(),
                        parse_mode="HTML"
                    )
                else:
                    # Fallback to text if image not found
                    await bot.send_message(
                        chat_id=user_id,
                        text=balance_message,
                        reply_markup=get_boost_active_keyboard(),
                        parse_mode="HTML"
                    )
                    sent_message = None

                if not cached_file_id and sent_message and getattr(sent_message, 'photo', None):
                    from app.dispatcher import admin_panel
                    admin_panel.set_file_id(photo_name, sent_message.photo[-1].file_id)
                    
                # Update last_notified rounded to the next full hour to align schedule
                latest_data = get_boost_data()
                if user_id_str in latest_data:
                    # round up to next full hour to avoid multiple sends within same hour window
                    rounded = (now_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                    latest_data[user_id_str]['last_notified'] = rounded.isoformat()
                    save_boost_data(latest_data)
                
                logging.info(f"Successfully sent time-based balance update to {user_id_str}.")

            except TelegramBadRequest as e:
                msg = str(e)
                if "chat not found" in msg or "user is blocked" in msg:
                    logging.warning(f"Chat not found or user {user_id_str} blocked the bot. Deactivating boost.")
                    stop_boost(user_id) # Deactivate boost to prevent further errors
                else:
                    logging.error(f"Failed to send balance update to {user_id_str} due to Telegram error: {e}", exc_info=True)
            except Exception as e:
                logging.error(f"An unexpected error occurred while sending balance update to {user_id_str}: {e}", exc_info=True) 