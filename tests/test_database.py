"""Тесты слоя БД: пользователи, заявки, сообщения, шаблоны, списки диалогов."""

import pytest

from bot.services import database


@pytest.mark.asyncio
async def test_init_db_creates_tables_and_seed_templates():
    await database.init_db()
    tpls = await database.list_templates()
    assert len(tpls) >= 4
    titles = {t["title"] for t in tpls}
    assert "Приветствие" in titles


@pytest.mark.asyncio
async def test_ensure_user_stub_and_save_message():
    await database.init_db()
    await database.ensure_user_stub(100, 200)
    await database.save_message(100, "user", "Привет")
    msgs = await database.get_messages(100)
    assert len(msgs) == 1
    assert msgs[0]["sender_type"] == "user"
    assert msgs[0]["text"] == "Привет"


@pytest.mark.asyncio
async def test_save_message_ignores_invalid_sender_and_empty_text():
    await database.init_db()
    await database.ensure_user_stub(1, 1)
    await database.save_message(1, "hacker", "x")
    await database.save_message(1, "user", "   ")
    assert await database.get_messages(1) == []


@pytest.mark.asyncio
async def test_save_user_and_phone_preservation():
    await database.init_db()
    await database.save_user(10, 99, "Иван", "Петров", "ivan", None)
    await database.update_user_phone(10, "+79990001122")
    await database.save_user(10, 99, "Иван", "Петров", "ivan", None)
    u = await database.get_user(10)
    assert u["phone"] == "+79990001122"
    assert u["first_name"] == "Иван"


@pytest.mark.asyncio
async def test_save_request_and_feedback_flow():
    await database.init_db()
    await database.save_user(20, 300, "A", None, None, None)
    rid = await database.save_request(20, 300, "Комод")
    assert rid > 0
    await database.update_feedback_status(rid, "no_response")
    pending = await database.get_latest_feedback_request(20)
    assert pending == (rid, "Комод")
    await database.update_feedback_status(rid, "ok")
    assert await database.get_latest_feedback_request(20) is None


@pytest.mark.asyncio
async def test_update_feedback_status_invalid_skips():
    await database.init_db()
    await database.save_user(21, 301, "B", None, None, None)
    rid = await database.save_request(21, 301, "Обувница")
    await database.update_feedback_status(rid, "not_a_real_status")  # noqa: S106
    # заявка остаётся в pending по умолчанию
    dialogs = await database.list_dialogs("all")
    row = next(d for d in dialogs if d["user_id"] == 21)
    assert row["last_feedback_status"] == "pending"


@pytest.mark.asyncio
async def test_templates_crud():
    await database.init_db()
    tid = await database.add_template("T1", "Текст один")
    assert tid > 0
    assert await database.update_template(tid, "T1x", "Новый")
    lst = await database.list_templates()
    assert any(t["id"] == tid and t["title"] == "T1x" for t in lst)
    assert await database.delete_template(tid)
    assert not await database.delete_template(tid)


@pytest.mark.asyncio
async def test_dialog_status():
    await database.init_db()
    await database.save_user(30, 400, "S", None, None, None)
    assert await database.update_dialog_status(30, "in_progress")
    u = await database.get_user(30)
    assert u["dialog_status"] == "in_progress"
    assert not await database.update_dialog_status(30, "invalid")


@pytest.mark.asyncio
async def test_list_dialogs_tabs_and_search():
    await database.init_db()
    await database.save_user(40, 500, "Мария", "Иванова", None, "+79991112233")
    rid = await database.save_request(40, 500, "Комод")
    await database.update_feedback_status(rid, "no_response")
    await database.save_message(40, "user", "тест")

    req = await database.list_dialogs("review_requested")
    assert any(d["user_id"] == 40 for d in req)

    await database.update_feedback_status(rid, "problem")
    prob = await database.list_dialogs("problems")
    assert any(d["user_id"] == 40 for d in prob)

    await database.update_feedback_status(rid, "ok")
    recv = await database.list_dialogs("review_received")
    assert any(d["user_id"] == 40 for d in recv)

    found = await database.list_dialogs("all", search="Мария")
    assert any(d["user_id"] == 40 for d in found)
    found_lower = await database.list_dialogs("all", search="мария")
    assert any(d["user_id"] == 40 for d in found_lower)
    found_phone = await database.list_dialogs("all", search="991112233")
    assert any(d["user_id"] == 40 for d in found_phone)
    await database.update_user_phone(40, "+7 (999) 111-22-33")
    found_phone_fmt = await database.list_dialogs("all", search="9991112233")
    assert any(d["user_id"] == 40 for d in found_phone_fmt)
