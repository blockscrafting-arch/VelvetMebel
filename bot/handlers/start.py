import logging

from maxapi import Router
from maxapi.types import BotStarted, MessageCreated, Command

from bot import texts
from bot.keyboards.inline import main_menu_kb
from bot.services.database import save_user

logger = logging.getLogger(__name__)
router = Router()


@router.bot_started()
async def on_bot_started(event: BotStarted):
    """Пользователь нажал 'Начать' — приветствие + главное меню."""
    logger.info(
        "bot_started: chat_id=%s user_id=%s",
        event.chat_id,
        getattr(event.user, "user_id", None),
    )
    kb = main_menu_kb()
    await event.bot.send_message(
        chat_id=event.chat_id,
        text=texts.WELCOME,
        attachments=[kb.as_markup()],
    )

    if event.user:
        try:
            await save_user(
                user_id=event.user.user_id,
                chat_id=event.chat_id,
                first_name=event.user.first_name,
                last_name=event.user.last_name,
                username=event.user.username,
            )
            logger.info("Новый пользователь: %s (%s)", event.user.first_name, event.user.user_id)
        except Exception:
            logger.exception("Ошибка сохранения пользователя: user_id=%s", event.user.user_id)


@router.message_created(Command("start"))
async def on_start_command(event: MessageCreated):
    """Команда /start — тоже показывает главное меню."""
    logger.info("command /start: chat_id=%s", event.chat.chat_id if event.chat else None)
    kb = main_menu_kb()
    await event.message.answer(
        text=texts.WELCOME,
        attachments=[kb.as_markup()],
    )

    if event.from_user:
        try:
            await save_user(
                user_id=event.from_user.user_id,
                chat_id=event.chat.chat_id,
                first_name=event.from_user.first_name,
                last_name=event.from_user.last_name,
                username=event.from_user.username,
            )
        except Exception:
            logger.exception("Ошибка сохранения пользователя: user_id=%s", event.from_user.user_id)
