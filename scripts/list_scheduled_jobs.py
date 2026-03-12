#!/usr/bin/env python3
"""
Показать запланированные задачи из БД планировщика (data/scheduler.db).
Запуск из корня проекта: python scripts/list_scheduled_jobs.py
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.config import MSK, settings  # noqa: E402


def main():
    db_path = settings.scheduler_db_path
    if not Path(db_path).exists():
        print(f"БД не найдена: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, next_run_time FROM apscheduler_jobs ORDER BY next_run_time"
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("Запланированных задач нет.")
        return

    print(f"Запланированные задачи (МСК), всего: {len(rows)}\n")
    print(f"{'ID':<35} {'Запуск (МСК)':<20}")
    print("-" * 55)
    for row in rows:
        job_id = row["id"]
        next_run = row["next_run_time"]
        if next_run is None:
            run_str = "(приостановлено)"
        else:
            dt = datetime.fromtimestamp(next_run, tz=MSK)
            run_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{job_id:<35} {run_str:<20}")


if __name__ == "__main__":
    main()
