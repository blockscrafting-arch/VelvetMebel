from maxapi.types import CallbackButton, LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot import texts


def main_menu_kb() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text=texts.BTN_GET_INSTRUCTION,
            payload="get_instruction",
        )
    )
    return builder


def models_kb() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for key, name in settings.models.names.items():
        builder.row(
            CallbackButton(
                text=name,
                payload=f"select_{key}",
            )
        )
    return builder


def feedback_kb() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text=texts.BTN_ASSEMBLY_OK,
            payload="assembly_ok",
        ),
        CallbackButton(
            text=texts.BTN_ASSEMBLY_PROBLEM,
            payload="assembly_problem",
        ),
    )
    return builder


def support_kb() -> InlineKeyboardBuilder | None:
    """Клавиатура с кнопкой-ссылкой на чат техподдержки. None если ссылка не задана."""
    if not (settings.support_chat_link and settings.support_chat_link.strip()):
        return None
    builder = InlineKeyboardBuilder()
    builder.row(
        LinkButton(
            text=texts.BTN_SUPPORT_CHAT,
            url=settings.support_chat_link.strip(),
        )
    )
    return builder
