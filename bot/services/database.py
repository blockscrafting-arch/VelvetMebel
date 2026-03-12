import logging
import aiosqlite

from bot.config import settings, now_msk

logger = logging.getLogger(__name__)
DB_PATH = settings.db_path


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                chat_id INTEGER NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                phone TEXT,
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
    now = now_msk()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO requests (user_id, chat_id, model, instruction_sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, chat_id, model, now),
        )
        await db.commit()
        return cursor.lastrowid


VALID_FEEDBACK_STATUSES = ("ok", "problem", "pending", "failed_send", "no_response")


async def update_feedback_status(request_id: int, status: str):
    if status not in VALID_FEEDBACK_STATUSES:
        logger.warning("update_feedback_status: неизвестный status=%r, запись пропущена", status)
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE requests
            SET feedback_status = ?, feedback_sent_at = ?
            WHERE id = ?
            """,
            (status, now_msk(), request_id),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_latest_pending_request(user_id: int) -> tuple[int, str] | None:
    """Возвращает (request_id, model) последнего запроса со статусом pending для user_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, model FROM requests
            WHERE user_id = ? AND feedback_status = 'pending'
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return (row[0], row[1]) if row else None
