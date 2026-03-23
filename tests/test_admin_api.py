"""HTTP-тесты веб-админки (FastAPI + TestClient)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bot.services import database


@pytest.fixture
def admin_app():
    """Импорт после autouse: DB_PATH уже подменён на tmp."""
    from admin.main import app

    return app


@pytest.fixture
def admin_client(admin_app):
    from admin.main import verify_admin

    admin_app.dependency_overrides[verify_admin] = lambda: "tester"
    with TestClient(admin_app) as client:
        yield client
    admin_app.dependency_overrides.clear()


@pytest.fixture
async def sample_user():
    await database.init_db()
    await database.save_user(42, 4242, "Клиент", "Тестовый", "cli", "+70000000042")
    return 42


def test_index_returns_html(admin_client):
    r = admin_client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Velvet" in r.text or "диалог" in r.text.lower() or len(r.text) > 100


def test_api_dialogs_requires_auth(admin_app, monkeypatch):
    monkeypatch.setattr("bot.config.settings.admin_password", "secret")
    monkeypatch.setattr("bot.config.settings.admin_username", "admin")
    admin_app.dependency_overrides.clear()
    with TestClient(admin_app) as client:
        assert client.get("/api/dialogs").status_code == 401
        r = client.get("/api/dialogs", auth=("admin", "secret"))
        assert r.status_code == 200
        assert "dialogs" in r.json()


def test_api_dialogs_with_override(admin_client):
    r = admin_client.get("/api/dialogs")
    assert r.status_code == 200
    assert r.json() == {"dialogs": []}


@pytest.mark.asyncio
async def test_api_messages_and_send(admin_client, sample_user):
    _ = sample_user
    r = admin_client.get("/api/messages/42")
    assert r.status_code == 200
    assert r.json()["messages"] == []

    with patch("admin.main.Bot") as BotCls:
        instance = MagicMock()
        instance.send_message = AsyncMock()
        instance.close_session = AsyncMock()
        BotCls.return_value = instance

        send = admin_client.post("/api/send/42", json={"text": "Ответ менеджера"})
        assert send.status_code == 200
        assert send.json() == {"ok": True}
        instance.send_message.assert_awaited_once()

    msgs = await database.get_messages(42)
    assert any(m["sender_type"] == "admin" and m["text"] == "Ответ менеджера" for m in msgs)


def test_api_send_404_unknown_user(admin_client):
    with patch("admin.main.Bot") as BotCls:
        BotCls.return_value.send_message = AsyncMock()
        BotCls.return_value.close_session = AsyncMock()
        r = admin_client.post("/api/send/99999", json={"text": "x"})
        assert r.status_code == 404


def test_api_send_validation_empty_body(admin_client):
    r = admin_client.post("/api/send/1", json={"text": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_templates_api(admin_client):
    await database.init_db()
    r = admin_client.get("/api/templates")
    assert r.status_code == 200
    initial = len(r.json()["templates"])

    cr = admin_client.post("/api/templates", json={"title": "API tpl", "text": "body"})
    assert cr.status_code == 200
    tid = cr.json()["id"]

    up = admin_client.put(
        f"/api/templates/{tid}",
        json={"title": "API tpl2", "text": "body2"},
    )
    assert up.status_code == 200

    dl = admin_client.delete(f"/api/templates/{tid}")
    assert dl.status_code == 200

    lst = admin_client.get("/api/templates").json()["templates"]
    assert len(lst) == initial


@pytest.mark.asyncio
async def test_dialog_status_api(admin_client):
    await database.init_db()
    await database.save_user(50, 5000, "X", None, None, None)
    r = admin_client.put("/api/dialogs/50/status", json={"status": "resolved"})
    assert r.status_code == 200
    u = await database.get_user(50)
    assert u["dialog_status"] == "resolved"


def test_dialog_status_api_bad_user(admin_client):
    r = admin_client.put("/api/dialogs/123456789/status", json={"status": "new"})
    assert r.status_code == 400


def test_admin_disabled_without_password(admin_app, monkeypatch):
    monkeypatch.setattr("bot.config.settings.admin_password", "")
    admin_app.dependency_overrides.clear()
    with TestClient(admin_app) as client:
        r = client.get("/api/dialogs", auth=("admin", "x"))
        assert r.status_code == 503
