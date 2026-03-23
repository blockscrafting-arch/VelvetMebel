import logging
import re
from typing import Any

import aiosqlite
from aiosqlite import Connection

from bot.config import settings, now_msk

logger = logging.getLogger(__name__)
DB_PATH = settings.db_path

# Статусы диалога в админке
DIALOG_STATUSES = ("new", "in_progress", "resolved")

DIALOG_TABS = frozenset({"all", "review_requested", "review_received", "problems"})


def _sql_ilower(value: object) -> str:
    """Нижний регистр для Unicode (кириллица); LIKE в SQLite без NOCASE для не-ASCII."""
    if value is None:
        return ""
    return str(value).lower()


def _sql_digits_only(value: object) -> str:
    """Только цифры — поиск телефона независимо от +, скобок, пробелов."""
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


async def _configure_db(db: Connection) -> None:
    """PRAGMA для совместной работы бота и админки (WAL + таймаут блокировок)."""
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA busy_timeout=5000;")
    await db.execute("PRAGMA foreign_keys=ON;")
    await db.create_function("ilower", 1, _sql_ilower)
    await db.create_function("digits_only", 1, _sql_digits_only)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                chat_id INTEGER NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                phone TEXT,
                dialog_status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                instruction_sent_at TIMESTAMP NOT NULL,
                feedback_sent_at TIMESTAMP,
                feedback_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user_created
            ON messages (user_id, created_at)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await _migrate_users_dialog_status(db)
        await _seed_default_templates(db)
        await db.commit()


async def _migrate_users_dialog_status(db: Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(users)")
    rows = await cursor.fetchall()
    col_names = {r[1] for r in rows}
    if "dialog_status" not in col_names:
        await db.execute(
            "ALTER TABLE users ADD COLUMN dialog_status TEXT DEFAULT 'new'"
        )


async def _seed_default_templates(db: Connection) -> None:
    cursor = await db.execute("SELECT COUNT(*) FROM templates")
    row = await cursor.fetchone()
    if row and row[0] > 0:
        return
    defaults = [
        ("Приветствие", "Здравствуйте! Чем могу помочь по сборке?"),
        (
            "Крепёж",
            "Проверьте, пожалуйста, что все крепления затянуты "
            "и ничего не перепутано по инструкции.",
        ),
        (
            "Видео",
            "Повторно отправляю ссылку на видеоинструкцию — "
            "если нужно, напишите модель мебели.",
        ),
        (
            "Гарантия",
            "По гарантийному случаю лучше написать в чат техподдержки — "
            "там быстрее оформят помощь.",
        ),
    ]
    await db.executemany(
        "INSERT INTO templates (title, text) VALUES (?, ?)",
        defaults,
    )


async def ensure_user_stub(user_id: int, chat_id: int) -> None:
    """
    Минимальная строка users до полного save_user (middleware логирует раньше хендлеров).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        await db.execute(
            """
            INSERT INTO users (user_id, chat_id, first_name, last_name, username, phone)
            VALUES (?, ?, NULL, NULL, NULL, NULL)
            ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id
            """,
            (user_id, chat_id),
        )
        await db.commit()


async def save_user(
    user_id: int,
    chat_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    phone: str | None = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        await db.execute(
            """
            INSERT INTO users (user_id, chat_id, first_name, last_name, username, phone)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                username = excluded.username,
                phone = CASE
                    WHEN excluded.phone IS NOT NULL AND excluded.phone != ''
                    THEN excluded.phone ELSE users.phone END
            """,
            (user_id, chat_id, first_name, last_name, username, (phone or "").strip()),
        )
        await db.commit()


async def update_user_phone(user_id: int, phone: str) -> None:
    """Обновить номер телефона пользователя."""
    phone = (phone or "").strip()
    if not phone:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        await db.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, user_id),
        )
        await db.commit()


async def save_request(
    user_id: int,
    chat_id: int,
    model: str,
) -> int:
    ts = now_msk().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cursor = await db.execute(
            """
            INSERT INTO requests (user_id, chat_id, model, instruction_sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, chat_id, model, ts),
        )
        await db.commit()
        return cursor.lastrowid


VALID_FEEDBACK_STATUSES = ("ok", "problem", "pending", "failed_send", "no_response")


async def update_feedback_status(request_id: int, status: str):
    if status not in VALID_FEEDBACK_STATUSES:
        logger.warning("update_feedback_status: неизвестный status=%r, запись пропущена", status)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        await db.execute(
            """
            UPDATE requests
            SET feedback_status = ?, feedback_sent_at = ?
            WHERE id = ?
            """,
            (status, now_msk().isoformat(), request_id),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_latest_feedback_request(user_id: int) -> tuple[int, str] | None:
    """
    Последняя заявка, по которой ждём ответ на опрос о сборке
    (вопрос уже отправлен, статус no_response).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cursor = await db.execute(
            """
            SELECT id, model FROM requests
            WHERE user_id = ? AND feedback_status = 'no_response'
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return (row[0], row[1]) if row else None


# Обратная совместимость имён
async def get_latest_pending_request(user_id: int) -> tuple[int, str] | None:
    return await get_latest_feedback_request(user_id)


async def save_message(user_id: int, sender_type: str, text: str) -> None:
    """Сохранить строку переписки для админки (user / bot / admin)."""
    if sender_type not in ("user", "bot", "admin"):
        logger.warning("save_message: неизвестный sender_type=%r", sender_type)
        return
    text = (text or "").strip()
    if not text:
        return
    # Ограничим длину на случай лимитов UI
    if len(text) > 8000:
        text = text[:7997] + "..."
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await _configure_db(db)
            await db.execute(
                """
                INSERT INTO messages (user_id, sender_type, text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, sender_type, text, now_msk().isoformat()),
            )
            await db.commit()
    except Exception:
        logger.exception("save_message: ошибка записи user_id=%s", user_id)


async def get_messages(user_id: int, limit: int = 500) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, sender_type, text, created_at
            FROM messages
            WHERE user_id = ?
            ORDER BY datetime(created_at) ASC, id ASC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def list_templates() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, text FROM templates ORDER BY id ASC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_template(title: str, text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cursor = await db.execute(
            "INSERT INTO templates (title, text) VALUES (?, ?)",
            (title.strip(), text.strip()),
        )
        await db.commit()
        return cursor.lastrowid


async def update_template(template_id: int, title: str, text: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cur = await db.execute(
            "UPDATE templates SET title = ?, text = ? WHERE id = ?",
            (title.strip(), text.strip(), template_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_template(template_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cur = await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        await db.commit()
        return cur.rowcount > 0


async def update_dialog_status(user_id: int, status: str) -> bool:
    if status not in DIALOG_STATUSES:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        cur = await db.execute(
            "UPDATE users SET dialog_status = ? WHERE user_id = ?",
            (status, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def list_dialogs(
    tab: str = "all",
    search: str | None = None,
) -> list[dict[str, Any]]:
    """
    Список пользователей для админки с последней заявкой и временем последнего сообщения.
    """
    if tab not in DIALOG_TABS:
        tab = "all"
    params: list[Any] = []
    where_extra = ""

    if search and search.strip():
        raw = search.strip()
        pat_lower = f"%{raw.lower()}%"
        pat_id = f"%{raw}%"
        digits_in_query = re.sub(r"\D", "", raw)
        search_parts = [
            "ilower(COALESCE(u.first_name,'')) LIKE ?",
            "ilower(COALESCE(u.last_name,'')) LIKE ?",
            "ilower(COALESCE(u.username,'')) LIKE ?",
            "CAST(u.user_id AS TEXT) LIKE ?",
        ]
        params.extend([pat_lower, pat_lower, pat_lower, pat_id])
        if digits_in_query:
            search_parts.append("digits_only(COALESCE(u.phone,'')) LIKE ?")
            params.append(f"%{digits_in_query}%")
        where_extra = " AND (" + " OR ".join(search_parts) + ")"

    sql = f"""
        SELECT
            u.user_id,
            u.chat_id,
            u.first_name,
            u.last_name,
            u.username,
            u.phone,
            u.dialog_status,
            u.created_at AS user_created_at,
            r.model AS last_model,
            r.feedback_status AS last_feedback_status,
            r.id AS last_request_id,
            (SELECT MAX(datetime(m.created_at)) FROM messages m WHERE m.user_id = u.user_id)
                AS last_message_at
        FROM users u
        LEFT JOIN requests r ON r.id = (
            SELECT id FROM requests WHERE user_id = u.user_id ORDER BY id DESC LIMIT 1
        )
        WHERE 1=1 {where_extra}
    """

    async with aiosqlite.connect(DB_PATH) as db:
        await _configure_db(db)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            st = d.get("last_feedback_status")
            if tab == "review_requested" and st != "no_response":
                continue
            if tab == "review_received" and st not in ("ok", "problem"):
                continue
            if tab == "problems" and st != "problem":
                continue
            result.append(d)

        def sort_key(x: dict) -> str:
            lm = x.get("last_message_at") or x.get("user_created_at") or ""
            return str(lm)

        result.sort(key=sort_key, reverse=True)
        return result
