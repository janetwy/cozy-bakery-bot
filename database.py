import sqlite3
from dataclasses import dataclass
from typing import Optional


DATABASE_PATH = "bakery_bot.db"


@dataclass
class CaptionSession:
    id: int
    discord_message_id: int
    discord_channel_id: int
    user_notes: str
    image_urls: str
    original_caption: str
    current_caption: str
    openai_response_id: Optional[str]


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS caption_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_message_id INTEGER UNIQUE NOT NULL,
                discord_channel_id INTEGER NOT NULL,
                user_notes TEXT NOT NULL,
                image_urls TEXT NOT NULL,
                original_caption TEXT NOT NULL,
                current_caption TEXT NOT NULL,
                openai_response_id TEXT
            )
        """)
        conn.commit()


def create_session(
    discord_message_id: int,
    discord_channel_id: int,
    user_notes: str,
    image_urls: str,
    caption: str,
    openai_response_id: Optional[str]
) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO caption_sessions (
                discord_message_id,
                discord_channel_id,
                user_notes,
                image_urls,
                original_caption,
                current_caption,
                openai_response_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            discord_message_id,
            discord_channel_id,
            user_notes,
            image_urls,
            caption,
            caption,
            openai_response_id
        ))

        conn.commit()
        return cursor.lastrowid


def get_session(session_id: int) -> Optional[CaptionSession]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT *
            FROM caption_sessions
            WHERE id = ?
        """, (session_id,)).fetchone()

        if row is None:
            return None

        return CaptionSession(**dict(row))


def update_session(
    session_id: int,
    caption: str,
    openai_response_id: Optional[str]
):
    with get_connection() as conn:
        conn.execute("""
            UPDATE caption_sessions
            SET current_caption = ?,
                openai_response_id = ?
            WHERE id = ?
        """, (
            caption,
            openai_response_id,
            session_id
        ))

        conn.commit()