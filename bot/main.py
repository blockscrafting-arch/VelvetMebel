import asyncio
import logging
import signal
import sys
from pathlib import Path

from maxapi import Bot, Dispatcher

from bot.config import settings
from bot.services.database import init_db
from apscheduler.schedulers.base import SchedulerNotRunningError
from bot.services.scheduler import init_scheduler, get_scheduler
from bot.handlers.start import router as start_router
from bot.handlers.phone import router as phone_router
from bot.handlers.instructions import router as instructions_router
from bot.handlers.feedback import router as feedback_router
from bot.middlewares import MessageLogMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("tzlocal").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


async def main():
    if not settings.bot.token:
        logger.error("MAX_BOT_TOKEN не задан! Проверьте .env файл.")
        sys.exit(1)

    bot = Bot(token=settings.bot.token)
    dp = Dispatcher()

    dp.outer_middleware(MessageLogMiddleware())
    dp.include_routers(start_router, phone_router, instructions_router, feedback_router)

    await init_db()
    logger.info("База данных инициализирована")

    creds_path = Path(settings.sheets.credentials_file)
    if settings.sheets.sheet_id and not creds_path.exists():
        logger.warning(
            "Google credentials не найден: %s. Запись в таблицу будет падать при первом обращении.",
            creds_path,
        )
    elif not settings.sheets.sheet_id:
        logger.warning("GOOGLE_SHEET_ID не задан. Запись в Google Таблицу отключена.")

    init_scheduler(bot)
    logger.info("Планировщик запущен")

    def _shutdown(*_args):
        sched = get_scheduler()
        if sched and sched.running:
            try:
                sched.shutdown(wait=False)
                logger.info("Планировщик остановлен")
            except SchedulerNotRunningError:
                pass
        logger.info("Получен сигнал завершения. Останавливаем поллинг...")
        dp.stop_polling()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("Бот запускается...")
    await bot.delete_webhook()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.close_session()
        logger.info("Сессия HTTP-клиента бота закрыта.")


if __name__ == "__main__":
    asyncio.run(main())
