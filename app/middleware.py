from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from services.admin_panel import AdminPanel
# Avoid circular import: import admin_panel lazily inside middleware methods

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Пытаемся получить объект пользователя из разных типов событий
        user = data.get("event_from_user")

        # Если событие не содержит информации о пользователе, пропускаем
        if not user:
            return await handler(event, data)

        # Проверяем режим обслуживания
        from app.dispatcher import admin_panel
        if admin_panel.get_maintenance_mode() and user.id not in admin_panel.admin_ids:
            message_text = admin_panel.get_maintenance_message()
            
            # Отвечаем в зависимости от типа события
            if event.message:
                await event.message.answer(message_text)
            elif event.callback_query:
                # Сначала отвечаем на колбэк, чтобы убрать "часики"
                await event.callback_query.answer()
                # Затем отправляем сообщение
                await event.callback_query.message.answer(message_text)
            
            # Прерываем дальнейшую обработку
            return
            
        return await handler(event, data)

class AdminCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")

        if not user:
            return await handler(event, data)

        from app.dispatcher import admin_panel
        if admin_panel.is_admin(user.id):
            return await handler(event, data)
        
        if isinstance(event, Message):
            await event.answer("Вибачте, ця функція доступна тільки адміністраторам.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Вибачте, ця функція доступна тільки адміністраторам.", show_alert=True)
            
        return 