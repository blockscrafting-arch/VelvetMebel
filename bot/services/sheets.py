import logging
import gspread
from google.oauth2.service_account import Credentials

from bot.config import settings, now_msk

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client: gspread.Client | None = None
_sheet: gspread.Spreadsheet | None = None


def _get_sheet() -> gspread.Worksheet:
    global _client, _sheet
    if _client is None:
        creds = Credentials.from_service_account_file(
            settings.sheets.credentials_file, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    if _sheet is None:
        _sheet = _client.open_by_key(settings.sheets.sheet_id)
    return _sheet.sheet1


def append_request(
    first_name: str,
    last_name: str | None,
    username: str | None,
    user_id: int,
    model_name: str,
):
    try:
        ws = _get_sheet()
        full_name = f"{first_name} {last_name}" if last_name else first_name
        # В C всегда включаем user_id для надёжного поиска при обновлении статуса
        nick = f"{user_id} @{username}" if username else str(user_id)
        now = now_msk().strftime("%Y-%m-%d %H:%M")

        ws.append_row(
            [now, full_name, nick, model_name, "Ожидание", "—"],
            value_input_option="USER_ENTERED",
        )
        logger.info("Записан запрос в Google Sheets: %s / %s", full_name, model_name)
    except Exception:
        logger.exception("Ошибка записи в Google Sheets")


def update_status(row_index: int, status: str):
    try:
        ws = _get_sheet()
        ws.update_cell(row_index, 5, status)
        logger.info("Обновлён статус в Google Sheets (строка %d): %s", row_index, status)
    except Exception:
        logger.exception("Ошибка обновления статуса в Google Sheets")


def find_row_by_user_and_model(user_id: int, model_name: str) -> int | None:
    """Ищет последнюю строку по user_id и модели для обновления статуса (последний запрос)."""
    try:
        ws = _get_sheet()
        all_rows = ws.get_all_values()
        uid_str = str(user_id)
        last_match = None
        for i, row in enumerate(all_rows, start=1):
            if len(row) >= 4 and (uid_str in row[2]) and row[3] == model_name:
                last_match = i
        return last_match
    except Exception:
        logger.exception("Ошибка поиска строки в Google Sheets")
    return None


def find_last_row_by_user(user_id: int) -> int | None:
    """Последняя строка в таблице, где в столбце C есть user_id (для обновления телефона в F)."""
    try:
        ws = _get_sheet()
        all_rows = ws.get_all_values()
        uid_str = str(user_id)
        last_match = None
        for i, row in enumerate(all_rows, start=1):
            if len(row) >= 3 and uid_str in row[2]:
                last_match = i
        return last_match
    except Exception:
        logger.exception("Ошибка поиска строки в Google Sheets")
    return None


def update_phone(row_index: int, phone: str) -> None:
    """Записать номер телефона в столбец F (колонка 6)."""
    try:
        ws = _get_sheet()
        ws.update_cell(row_index, 6, phone)
        logger.info("Обновлён телефон в Google Sheets (строка %d): %s", row_index, phone)
    except Exception:
        logger.exception("Ошибка обновления телефона в Google Sheets")
