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


# VCARD: TEL;TYPE=cell:79788643335 или TEL:79001234567
_VCARD_TEL_RE = re.compile(r"TEL(?:;[^:]*)?:([\d\s+\-]+)", re.IGNORECASE)


def _phone_from_vcard(vcf_str: str) -> str | None:
    """Извлечь первый номер телефона из строки VCARD (payload.vcf_info в MAX)."""
    if not vcf_str or not isinstance(vcf_str, str):
        return None
    m = _VCARD_TEL_RE.search(vcf_str)
    if m:
        return m.group(1).strip()
    return None


def _get_phone_from_payload(payload) -> str | None:
    """Достать номер из payload (объект или dict), разные варианты имён полей."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        vcf = payload.get("vcf_info")
        if vcf:
            phone = _phone_from_vcard(vcf)
            if phone:
                return phone
    if hasattr(payload, "vcf_info") and getattr(payload, "vcf_info", None):
        phone = _phone_from_vcard(str(getattr(payload, "vcf_info")))
        if phone:
            return phone
    for key in ("phone_number", "phoneNumber", "phone"):
        if hasattr(payload, key):
            val = getattr(payload, key, None)
            if val and str(val).strip():
                return str(val).strip()
        if isinstance(payload, dict) and payload.get(key):
            return str(payload[key]).strip()
    return None


def _extract_phone_from_contact_attachment(attachments: list) -> str | None:
    """Из вложений сообщения извлечь номер (type=contact или любой payload с phone)."""
    if not attachments:
        return None
    contact_types = ("contact", "request_contact", "contact_shared", "vcard")
    for att in attachments:
        att_type = getattr(att, "type", None) or (
            att.get("type") if isinstance(att, dict) else None
        )
        payload = getattr(att, "payload", None) or (
            att.get("payload") if isinstance(att, dict) else None
        )
        if att_type in contact_types:
            phone = _get_phone_from_payload(payload)
            if phone:
                return phone
            if isinstance(att, dict) and att.get("phone_number"):
                return str(att["phone_number"]).strip()
            if hasattr(att, "phone_number") and getattr(att, "phone_number", None):
                return str(getattr(att, "phone_number")).strip()
        phone = _get_phone_from_payload(att) or _get_phone_from_payload(payload)
        if phone:
            return phone
    return None


def _attachment_to_dict(att) -> dict:
    """Безопасно превратить вложение в dict для лога."""
    if att is None:
        return {}
    if isinstance(att, dict):
        return att
    if hasattr(att, "model_dump"):
        return att.model_dump()
    if hasattr(att, "dict"):
        return att.dict()
    return {"type": type(att).__name__, "repr": str(att)[:200]}


@router.message_created(F.message.body.attachments)
async def on_contact_shared(event: MessageCreated):
    """Пользователь нажал «Поделиться номером» — контакт пришёл во вложениях."""
    attachments = event.message.body.attachments or []
    phone = _extract_phone_from_contact_attachment(attachments)
    if not phone:
        logger.info(
            "contact_shared: телефон не извлечён, вложения=%s",
            [_attachment_to_dict(a) for a in attachments],
        )
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
