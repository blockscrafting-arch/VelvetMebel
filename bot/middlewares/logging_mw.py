"""
Глобальный middleware: пишет входящие текстовые сообщения пользователей в БД для админки.
См. maxapi BaseMiddleware: https://context7.com/love-apples/maxapi
"""
import logging
from typing import Any, Awaitable, Callable

from maxapi.enums.update import UpdateType
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import MessageCreated

from bot.services import database

logger = logging.getLogger(__name__)


class MessageLogMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        if getattr(event_object, "update_type", None) == UpdateType.MESSAGE_CREATED:
            if isinstance(event_object, MessageCreated):
                body = event_object.message.body
                text = (getattr(body, "text", None) or "").strip()
                sender = getattr(event_object.message, "sender", None)
                if text and sender and not getattr(sender, "is_bot", False):
                    uid = getattr(sender, "user_id", None)
                    chat_id, _u2 = event_object.get_ids()
                    if uid is not None and chat_id is not None:
                        try:
                            await database.ensure_user_stub(int(uid), int(chat_id))
                            await database.save_message(int(uid), "user", text)
                        except Exception:
                            logger.exception(
                                "MessageLogMiddleware: не удалось сохранить сообщение user_id=%s",
                                uid,
                            )
        return await handler(event_object, data)
