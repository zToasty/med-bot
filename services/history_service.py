"""
Персистентное хранение истории диалогов в SQLite.
"""

import sqlite3
import logging

from config import DB_PATH


logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 40
MAX_APPROX_TOKENS = 30000


def init_db() -> None:
    """Создаёт таблицу history, если её ещё нет."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON history (user_id, id)
        """)
        conn.commit()
        logger.info("✅ БД истории инициализирована: %s", DB_PATH)
    finally:
        conn.close()


def append_message(user_id: int, role: str, content: str) -> None:
    """Добавляет одно сообщение в историю."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        conn.commit()
    finally:
        conn.close()


def load_history(user_id: int) -> list[dict[str, str]]:
    """
    Загружает последние сообщения пользователя.
    Применяет те же лимиты, что раньше использовал trim_history:
    - не более MAX_HISTORY_MESSAGES
    - не более MAX_APPROX_TOKENS * 4 символов суммарно
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, id
                FROM history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) sub ORDER BY id ASC
            """,
            (user_id, MAX_HISTORY_MESSAGES),
        ).fetchall()
    finally:
        conn.close()

    messages = [{"role": role, "content": content} for role, content in rows]

    # Обрезаем по символам (как раньше trim_history)
    total_chars = sum(len(m["content"]) for m in messages)
    while total_chars > MAX_APPROX_TOKENS * 4 and len(messages) > 2:
        removed = messages.pop(0)
        total_chars -= len(removed["content"])

    return messages


def clear_history(user_id: int) -> None:
    """Очищает историю конкретного пользователя."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
