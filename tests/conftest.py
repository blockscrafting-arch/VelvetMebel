"""Общие фикстуры: изолированная SQLite для каждого теста."""

import pytest


@pytest.fixture(autouse=True)
def isolate_sqlite_db(tmp_path, monkeypatch):
    """Не трогаем data/bot.db проекта — каждый тест со своим файлом."""
    db_path = tmp_path / "test_bot.db"
    monkeypatch.setattr("bot.services.database.DB_PATH", str(db_path))
    yield db_path
