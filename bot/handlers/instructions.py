import logging

from maxapi import F, Router
from maxapi.types import MessageCallback

from bot import texts
from bot.config import settings
from bot.keyboards.inline import models_kb
from bot.services.database import save_user, save_request
from bot.services.scheduler import schedule_feedback
from bot.services import sheets

logger = logging.getLogger(__name__)
router = Router()


@router.message_callback(F.callback.payload == "get_instruction")
async def on_get_instruction(event: MessageCallback):
    """Нажата кнопка 'Получить видео инструкцию' — показать выбор модели."""
    kb = models_kb()
    await event.answer(notification="")
    await event.message.answer(text=texts.CHOOSE_MODEL, attachments=[kb.as_markup()])


@router.message_callback(F.callback.payload.in_(["model_1", "model_2", "model_3"]))
async def on_select_model(event: MessageCallback):
    """Выбрана конкретная модель — отправить инструкцию и запланировать follow-up."""
    model_key = event.callback.payload
    model_name = settings.models.names.get(model_key, model_key)
    video_url = settings.models.videos.get(model_key, "")

    user = event.from_user
    chat_id = event.message.recipient.chat_id

    await event.message.answer(
        text=texts.INSTRUCTION_SENT.format(
            model_name=model_name,
            video_url=video_url if video_url else "(видео будет добавлено)",
        ),
    )

    if user:
        try:
            await save_user(
                user_id=user.user_id,
                chat_id=chat_id,
                first_name=user.first_name,
                last_name=user.last_name,
                username=user.username,
            )
            request_id = await save_request(
                user_id=user.user_id,
                chat_id=chat_id,
                model=model_name,
            )
            sheets.append_request(
                first_name=user.first_name or "—",
                last_name=user.last_name,
                username=user.username,
                user_id=user.user_id,
                model_name=model_name,
            )
            schedule_feedback(
                chat_id=chat_id,
                user_id=user.user_id,
                request_id=request_id,
                model_name=model_name,
            )
            logger.info(
                "Выдана инструкция: user=%s, model=%s, request_id=%s",
                user.user_id,
                model_name,
                request_id,
            )
        except Exception:
            logger.exception(
                "Ошибка при сохранении запроса/планировании follow-up: user=%s, model=%s",
                user.user_id,
                model_name,
            )
