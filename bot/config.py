import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class BotConfig:
    token: str = field(default_factory=lambda: os.getenv("MAX_BOT_TOKEN", ""))


@dataclass
class SheetsConfig:
    sheet_id: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEET_ID", ""))
    credentials_file: str = field(
        default_factory=lambda: str(
            BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        )
    )


@dataclass
class ModelsConfig:
    # Velvet Mebel: утверждённые названия моделей
    names: dict[str, str] = field(default_factory=lambda: {
        "model_1": "Комод",
        "model_2": "Обувница",
        "model_3": "Обувница с ящиком",
    })
    videos: dict[str, str] = field(default_factory=lambda: {
        "model_1": os.getenv("MODEL_1_VIDEO", ""),
        "model_2": os.getenv("MODEL_2_VIDEO", ""),
        "model_3": os.getenv("MODEL_3_VIDEO", ""),
    })


@dataclass
class Settings:
    bot: BotConfig = field(default_factory=BotConfig)
    sheets: SheetsConfig = field(default_factory=SheetsConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    feedback_delay_hours: int = field(
        default_factory=lambda: _safe_int(os.getenv("FEEDBACK_DELAY_HOURS", "24"), 24)
    )
    support_chat_link: str = field(
        default_factory=lambda: os.getenv("SUPPORT_CHAT_LINK", "")
    )
    db_path: str = field(
        default_factory=lambda: str(DATA_DIR / "bot.db")
    )
    scheduler_db_path: str = field(
        default_factory=lambda: str(DATA_DIR / "scheduler.db")
    )


settings = Settings()
