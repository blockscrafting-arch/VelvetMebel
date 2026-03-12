import logging

from maxapi import F, Router
from maxapi.types import MessageCallback

from bot import texts
from bot.keyboards.inline import support_kb
from bot.services.database import get_latest_pending_request, update_feedback_status
from bot.services import sheets

logger = logging.getLogger(__name__)
router = Router()


async def _update_feedback_and_sheets(user_id: int, status: str, status_label: str):
    """Обновляет статус в БД и в Google Таблице для последнего pending-запроса."""
    pending = await get_latest_pending_request(user_id)
    if not pending:
        return
    request_id, model_name = pending
    await update_feedback_status(request_id, status)
    row_index = sheets.find_row_by_user_and_model(user_id, model_name)
    if row_index:
        sheets.update_status(row_index, status_label)


@router.message_callback(F.callback.payload == "assembly_ok")
async def on_assembly_ok(event: MessageCallback):
    """«Да» — просим отзыв на Wildberries, обновляем статус в БД и Sheets."""
    await event.answer(new_text=texts.FEEDBACK_OK)
    if event.from_user:
        await _update_feedback_and_sheets(event.from_user.user_id, "ok", "Успешно")
        logger.info("Сборка OK: user=%s", event.from_user.user_id)
    else:
        logger.info("Сборка OK: user=?")


@router.message_callback(F.callback.payload == "assembly_problem")
async def on_assembly_problem(event: MessageCallback):
    """«Нет» — отправляем текст и кнопку-ссылку на чат техподдержки (если задана), обновляем статус."""
    kb = support_kb()
    if kb:
        await event.answer(new_text=texts.FEEDBACK_PROBLEM, keyboard=kb.as_markup())
    else:
        await event.answer(new_text=texts.FEEDBACK_PROBLEM)
    if event.from_user:
        await _update_feedback_and_sheets(event.from_user.user_id, "problem", "Проблемы")
        logger.info("Сборка PROBLEM: user=%s", event.from_user.user_id)
    else:
        logger.info("Сборка PROBLEM: user=?")
