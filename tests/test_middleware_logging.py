"""Тесты MessageLogMiddleware: запись входящих текстовых сообщений."""

from unittest.mock import AsyncMock

import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.enums.update import UpdateType
from maxapi.types import MessageCreated
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.users import User

from bot.middlewares.logging_mw import MessageLogMiddleware
from bot.services import database


def _message_created_event(*, uid: int, chat_id: int, text: str) -> MessageCreated:
    sender = User(
        user_id=uid,
        first_name="U",
        is_bot=False,
        last_activity_time=0,
    )
    body = MessageBody(mid="m1", seq=1, text=text)
    msg = Message(
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=chat_id),
        timestamp=1,
        sender=sender,
        body=body,
    )
    return MessageCreated(timestamp=1, message=msg)


@pytest.mark.asyncio
async def test_middleware_logs_user_text_and_calls_handler():
    await database.init_db()
    mw = MessageLogMiddleware()
    handler = AsyncMock(return_value="done")
    ev = _message_created_event(uid=777, chat_id=888, text="  Сообщение клиента  ")

    assert ev.update_type == UpdateType.MESSAGE_CREATED
    result = await mw(handler, ev, {})
    assert result == "done"
    handler.assert_awaited_once()

    msgs = await database.get_messages(777)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "Сообщение клиента"
    assert msgs[0]["sender_type"] == "user"


@pytest.mark.asyncio
async def test_middleware_skips_empty_and_bot_sender():
    await database.init_db()
    mw = MessageLogMiddleware()
    handler = AsyncMock(return_value="ok")

    bot_user = User(
        user_id=1,
        first_name="Bot",
        is_bot=True,
        last_activity_time=0,
    )
    body = MessageBody(mid="m2", seq=2, text="hi")
    msg = Message(
        recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=1),
        timestamp=1,
        sender=bot_user,
        body=body,
    )
    ev_bot = MessageCreated(timestamp=1, message=msg)
    await mw(handler, ev_bot, {})
    assert await database.get_messages(1) == []

    ev_empty = _message_created_event(uid=2, chat_id=2, text="   ")
    await mw(handler, ev_empty, {})
    assert await database.get_messages(2) == []
