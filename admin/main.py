"""
Веб-админка для менеджера: диалоги, переписка, шаблоны, отправка от имени бота.

Запуск (из корня репозитория):
  uvicorn admin.main:app --host 0.0.0.0 --port 8000

Документация MAX Bot API (отправка сообщений):
  https://dev.max.ru/docs-api/methods/POST/messages

Библиотека maxapi (Bot.send_message):
  Context7 /love-apples/maxapi
"""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from maxapi import Bot
from pydantic import BaseModel, Field

from bot.config import settings
from bot.services import database

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте админки убедимся, что таблицы и шаблоны созданы
    try:
        await database.init_db()
        logger.info("Admin DB init OK")
    except Exception:
        logger.exception("Admin DB init failed")
    yield

security = HTTPBasic(auto_error=False)

app = FastAPI(title="Velvet Mebel — админка MAX-бота", version="1.0.0", lifespan=lifespan)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def verify_admin(credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
    if not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_PASSWORD не задан в .env — админка отключена",
        )
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(
        credentials.username.strip().encode("utf-8"),
        settings.admin_username.encode("utf-8"),
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.admin_password.encode("utf-8"),
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def index_page(_username: str = Depends(verify_admin)) -> HTMLResponse:
    path = TEMPLATES_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(500, "Шаблон index.html не найден")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/api/dialogs", tags=["api"])
async def api_dialogs(
    tab: str = "all",
    search: str | None = None,
    _username: str = Depends(verify_admin),
):
    valid = ("all", "review_requested", "review_received", "problems")
    if tab not in valid:
        tab = "all"
    rows = await database.list_dialogs(tab=tab, search=search)
    return {"dialogs": rows}


@app.get("/api/messages/{user_id}", tags=["api"])
async def api_messages(user_id: int, _username: str = Depends(verify_admin)):
    return {"messages": await database.get_messages(user_id)}


class SendBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


@app.post("/api/send/{user_id}", tags=["api"])
async def api_send(user_id: int, body: SendBody, _username: str = Depends(verify_admin)):
    user = await database.get_user(user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    chat_id = user["chat_id"]
    text = body.text.strip()
    bot = Bot(token=settings.bot.token)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.exception("admin send_message failed user_id=%s", user_id)
        raise HTTPException(502, detail=str(e)) from e
    finally:
        try:
            await bot.close_session()
        except Exception:
            logger.exception("close_session after admin send")
    await database.save_message(user_id, "admin", text)
    return {"ok": True}


@app.get("/api/templates", tags=["api"])
async def api_templates_list(_username: str = Depends(verify_admin)):
    return {"templates": await database.list_templates()}


class TemplateBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=4000)


@app.post("/api/templates", tags=["api"])
async def api_template_create(body: TemplateBody, _username: str = Depends(verify_admin)):
    tid = await database.add_template(body.title, body.text)
    return {"id": tid}


@app.put("/api/templates/{template_id}", tags=["api"])
async def api_template_update(
    template_id: int, body: TemplateBody, _username: str = Depends(verify_admin)
):
    ok = await database.update_template(template_id, body.title, body.text)
    if not ok:
        raise HTTPException(404, "Шаблон не найден")
    return {"ok": True}


@app.delete("/api/templates/{template_id}", tags=["api"])
async def api_template_delete(template_id: int, _username: str = Depends(verify_admin)):
    ok = await database.delete_template(template_id)
    if not ok:
        raise HTTPException(404, "Шаблон не найден")
    return {"ok": True}


class DialogStatusBody(BaseModel):
    status: Literal["new", "in_progress", "resolved"]


@app.put("/api/dialogs/{user_id}/status", tags=["api"])
async def api_dialog_status(
    user_id: int, body: DialogStatusBody, _username: str = Depends(verify_admin)
):
    ok = await database.update_dialog_status(user_id, body.status)
    if not ok:
        raise HTTPException(400, "Не удалось обновить статус")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "admin.main:app",
        host=settings.admin_host,
        port=settings.admin_port,
        reload=False,
    )
