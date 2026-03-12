"""
Обработка номера телефона (опционально по ТЗ).
Пользователь может: нажать «Поделиться номером» (контакт) или написать номер в чат.
"""
import logging
import re

from maxapi import F, Router
from maxapi.types import MessageCreated

from bot import texts
from bot.services.database import update_user_phone
from bot.services import sheets

logger = logging.getLogger(__name__)
router = Router()

def _normalize_phone(raw: str) -> str:
    """Оставить только цифры и ведущий + при наличии."""
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 10:
        if digits.startswith("8") and len(digits) == 11:
            return "+7" + digits[1:]
        if digits.startswith("7") and len(digits) == 11:
            return "+" + digits
        if len(digits) == 10:
            return "+7" + digits
        return "+" + digits if not raw.startswith("+") else "+" + digits
    return raw


def _extract_phone_from_contact_attachment(attachments: list) -> str | None:
    """Из вложений сообщения извлечь номер из контакта (type=contact)."""
    if not attachments:
        return None
    for att in attachments:
        att_type = getattr(att, "type", None) or (
            att.get("type") if isinstance(att, dict) else None
        )
        if att_type != "contact":
            continue
        payload = getattr(att, "payload", None) or (
            att.get("payload") if isinstance(att, dict) else None
        )
        if not payload:
            continue
        if hasattr(payload, "phone_number"):
            return getattr(payload, "phone_number", None)
        if hasattr(payload, "phone"):
            return getattr(payload, "phone", None)
        if isinstance(payload, dict):
            return payload.get("phone_number") or payload.get("phone")
    return None


@router.message_created(F.message.body.attachments)
async def on_contact_shared(event: MessageCreated):
    """Пользователь нажал «Поделиться номером» — контакт пришёл во вложениях."""
    attachments = event.message.body.attachments or []
    phone = _extract_phone_from_contact_attachment(attachments)
    if not phone:
        return
    phone = _normalize_phone(phone)
    if len(phone) < 10:
        return
    user = event.from_user
    chat_id = event.chat.chat_id if event.chat else None
    if not user or not chat_id:
        return
    try:
        await update_user_phone(user.user_id, phone)
        row_index = sheets.find_last_row_by_user(user.user_id)
        if row_index:
            sheets.update_phone(row_index, phone)
        await event.message.answer(text=texts.PHONE_SAVED)
        logger.info("Сохранён телефон: user_id=%s", user.user_id)
    except Exception:
        logger.exception("Ошибка сохранения телефона: user_id=%s", user.user_id)
        await event.message.answer(text="Не удалось сохранить номер. Попробуйте позже.")


@router.message_created(F.message.body.text.regexp(r"^[\d\s+\-()]{10,20}$"))
async def on_phone_text(event: MessageCreated):
    """Пользователь написал в чат текст, похожий на номер телефона."""
    if event.message.body.attachments and _extract_phone_from_contact_attachment(
        event.message.body.attachments
    ):
        return
    text = (event.message.body.text or "").strip()
    phone = _normalize_phone(text)
    if len(phone) < 10:
        return
    user = event.from_user
    if not user:
        return
    try:
        await update_user_phone(user.user_id, phone)
        row_index = sheets.find_last_row_by_user(user.user_id)
        if row_index:
            sheets.update_phone(row_index, phone)
        await event.message.answer(text=texts.PHONE_SAVED)
        logger.info("Сохранён телефон (текст): user_id=%s", user.user_id)
    except Exception:
        logger.exception("Ошибка сохранения телефона: user_id=%s", user.user_id)
