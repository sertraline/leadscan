from logging import Logger
from typing import Any, Awaitable, Callable, cast

from aiogram import BaseMiddleware
from aiogram.types import (
    TelegramObject,
    Update
)
from models import users


class StructLoggingMiddleware(BaseMiddleware):
    um: users.UserManager
    log: Logger

    def __init__(self, user_manager, log):
        self.um = user_manager
        self.log = log
        super(StructLoggingMiddleware, self).__init__()

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event = cast(Update, event)
        # Нам нужно узнать from_user из события и внести его в базу данных
        username = None
        from_user = None

        if event.message:
            message = event.message
            from_user = message.from_user
        elif event.callback_query:
            c = event.callback_query
            from_user = c.from_user
        elif event.inline_query:
            query = event.inline_query
            from_user = query.from_user
        elif cm := event.chat_member:
            if cm.new_chat_member:
                from_user = cm.new_chat_member.user
        if not from_user:
            return await handler(event, data)

        telegram_id = from_user.id
        username = from_user.username

        if telegram_id:
            data["user"] = await self.um.user_entry(
                telegram_id=telegram_id,
                username=username
            )
        return await handler(event, data)
