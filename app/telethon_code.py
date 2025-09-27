import logging
import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = "telethon.session"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TelethonClient:
    def __init__(self, session_name, api_id, api_hash):
        logger.info("Initializing Telethon client...")
        self.session_name = session_name
        self.api_id = api_id
        self.api_hash = api_hash
        if not self.api_id or not self.api_hash:
            raise ValueError("API_ID and API_HASH must be set in environment variables.")
        self.client = TelegramClient(self.session_name, int(self.api_id), self.api_hash)
        self.is_connected = False
        self.lock = asyncio.Lock()

    async def initialize(self):
        """
        Connects the client and ensures the user is authorized.
        If not authorized, it will trigger the interactive login flow in the console.
        """
        async with self.lock:
            # The .start() method handles everything: connection, authorization, and interactive login.
            try:
                if not self.client.is_connected():
                    # This will connect and prompt for login details in the console if session is invalid
                    await self.client.start()
                
                me = await self.client.get_me()
                if me:
                    self.is_connected = True
                    logger.info(f"✅ Telethon client initialized and connected successfully as {me.first_name}.")
                else:
                    # This case should ideally not be reached if .start() is successful
                    self.is_connected = False
                    logger.error("❌ Failed to initialize Telethon client. Could not get user info after start.")
            except Exception as e:
                self.is_connected = False
                logger.error(f"❌ An error occurred during Telethon client initialization: {e}", exc_info=True)


    async def disconnect(self):
        async with self.lock:
            if self.client.is_connected():
                logger.info("Disconnecting Telethon client...")
                await self.client.disconnect()
                self.is_connected = False
                logger.info("✅ Telethon client disconnected successfully.")

    async def send_message(self, entity, message):
        async with self.lock:
            if not self.is_connected:
                await self.initialize()
            if not self.is_connected:
                raise ConnectionError("Telethon client is not connected.")
            return await self.client.send_message(entity, message)

    async def get_messages(self, entity, limit=1):
        messages = []
        async with self.lock:
            if not self.is_connected:
                await self.initialize()
            if not self.is_connected:
                raise ConnectionError("Telethon client is not connected.")
            async for message in self.client.iter_messages(entity, limit=limit):
                messages.append(message)
        return messages

# Singleton instance
telethon_client = TelethonClient(SESSION_NAME, API_ID, API_HASH) 