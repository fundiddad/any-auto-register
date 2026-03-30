"""LuckMail 复用记录存储。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .db import DATABASE_URL


def _db_path() -> Path:
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix):
        raise RuntimeError(f"Unsupported database url: {DATABASE_URL}")
    return Path(__file__).resolve().parent.parent / DATABASE_URL[len(prefix):]


@contextmanager
def _connect():
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS luckmail_reuse_records (
                email TEXT NOT NULL,
                token TEXT NOT NULL,
                project_code TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (email, token, project_code)
            )
            """
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


def load_blocked_keys() -> tuple[set[str], set[str]]:
    # success / failed 都不再参与自动复用，避免重复消耗或反复命中坏邮箱。
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT email, token
            FROM luckmail_reuse_records
            WHERE status IN ('success', 'failed')
            """
        ).fetchall()

    blocked_emails: set[str] = set()
    blocked_tokens: set[str] = set()
    for email, token in rows:
        email_text = str(email or "").strip().lower()
        token_text = str(token or "").strip()
        if email_text:
            blocked_emails.add(email_text)
        if token_text:
            blocked_tokens.add(token_text)
    return blocked_emails, blocked_tokens


def save_result(
    *,
    email: str,
    token: str,
    project_code: str,
    status: str,
    last_error: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO luckmail_reuse_records (
                email, token, project_code, status, last_error, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email, token, project_code) DO UPDATE SET
                status = excluded.status,
                last_error = excluded.last_error,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(email or "").strip().lower(),
                str(token or "").strip(),
                str(project_code or "").strip(),
                str(status or "").strip(),
                str(last_error or ""),
            ),
        )
