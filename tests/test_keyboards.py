"""Тесты разметки inline-клавиатур (главное меню, модели, опрос)."""

import pytest
from maxapi.enums.button_type import ButtonType

from bot.keyboards import inline


@pytest.fixture
def support_link(monkeypatch):
    monkeypatch.setattr("bot.config.settings.support_chat_link", "https://max.ru/join/test")
    yield "https://max.ru/join/test"
    monkeypatch.setattr("bot.config.settings.support_chat_link", "")


def test_main_menu_without_support_has_two_button_rows():
    mk = inline.main_menu_kb().as_markup()
    assert len(mk.payload.buttons) == 2


def test_main_menu_with_support_has_three_rows(support_link):
    _ = support_link
    mk = inline.main_menu_kb().as_markup()
    assert len(mk.payload.buttons) == 3
    second_row = mk.payload.buttons[1]
    assert len(second_row) == 1
    assert second_row[0].type == ButtonType.LINK


def test_models_kb_has_three_models():
    mk = inline.models_kb().as_markup()
    assert len(mk.payload.buttons) == 3
    payloads = {row[0].payload for row in mk.payload.buttons}
    assert payloads == {"model_1", "model_2", "model_3"}


def test_feedback_kb_two_callbacks():
    mk = inline.feedback_kb().as_markup()
    assert len(mk.payload.buttons) == 1
    assert len(mk.payload.buttons[0]) == 2


def test_support_kb_none_without_link():
    assert inline.support_kb() is None


def test_support_kb_with_link(support_link):
    _ = support_link
    kb = inline.support_kb()
    assert kb is not None
    mk = kb.as_markup()
    assert len(mk.payload.buttons) == 1
