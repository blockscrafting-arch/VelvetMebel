import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from maxapi import Bot

from bot.config import settings
from bot import texts
from bot.keyboards.inline import feedback_kb
from bot.services import database, sheets

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def init_scheduler(bot: Bot) -> AsyncIOScheduler:
    global _scheduler, _bot
    _bot = bot
    jobstores = {
        "default": SQLAlchemyJobStore(
            url=f"sqlite:///{settings.scheduler_db_path}"
        )
    }
    _scheduler = AsyncIOScheduler(jobstores=jobstores)
    _scheduler.start()
    logger.info("Планировщик инициализирован, БД: %s", settings.scheduler_db_path)
    return _scheduler


def schedule_feedback(
    chat_id: int,
    user_id: int,
    request_id: int,
    model_name: str,
):
    if _scheduler is None:
        raise RuntimeError("Планировщик не инициализирован")

    run_at = datetime.now() + timedelta(hours=settings.feedback_delay_hours)
    job_id = f"feedback_{user_id}_{request_id}"

    _scheduler.add_job(
        send_feedback_message,
        "date",
        run_date=run_at,
        id=job_id,
        replace_existing=True,
        kwargs={
            "chat_id": chat_id,
            "user_id": user_id,
            "request_id": request_id,
            "model_name": model_name,
        },
    )
    logger.info(
        "Запланировано сообщение о сборке: user=%s, model=%s, время=%s",
        user_id,
        model_name,
        run_at.strftime("%Y-%m-%d %H:%M"),
    )


async def send_feedback_message(
    chat_id: int,
    user_id: int,
    request_id: int,
    model_name: str,
):
    if _bot is None:
        logger.error("Бот не инициализирован для отправки отложенного сообщения")
        return

    try:
        kb = feedback_kb()
        await _bot.send_message(
            chat_id=chat_id,
            text=texts.FEEDBACK_QUESTION.format(model_name=model_name),
            attachments=[kb.as_markup()],
        )
        logger.info(
            "Отправлено сообщение о сборке: user=%s, request=%s",
            user_id,
            request_id,
        )
    except Exception:
        logger.exception(
            "Ошибка отправки отложенного сообщения: user=%s", user_id
        )
        try:
            await database.update_feedback_status(request_id, "failed_send")
        except Exception:
            logger.exception("Не удалось обновить статус запроса %s на failed_send", request_id)
