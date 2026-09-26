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
    is_finalized: bool
    approved_version_id: Optional[int]
    finalized_discord_message_id: Optional[int]


@dataclass
class CaptionVersion:
    id: int
    session_id: int
    version_number: int
    caption: str
    openai_response_id: Optional[str]
    revision_type: str


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    with get_connection() as conn:

        # Main caption session
        conn.execute("""
            CREATE TABLE IF NOT EXISTS caption_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_message_id INTEGER UNIQUE NOT NULL,
                discord_channel_id INTEGER NOT NULL,
                user_notes TEXT NOT NULL,
                image_urls TEXT NOT NULL,
                is_finalized INTEGER NOT NULL DEFAULT 0,
                approved_version_id INTEGER,
                finalized_discord_message_id INTEGER
            )
        """)

        try:
            conn.execute("""
                ALTER TABLE caption_sessions
                ADD COLUMN finalized_discord_message_id INTEGER
            """)
        except sqlite3.OperationalError:
            # Column already exists
            pass

        # Individual caption versions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS caption_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                caption TEXT NOT NULL,
                openai_response_id TEXT,
                revision_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id)
                    REFERENCES caption_sessions(id),

                UNIQUE(session_id, version_number)
            )
        """)

        conn.commit()


def create_session(
    discord_message_id: int,
    discord_channel_id: int,
    user_notes: str,
    image_urls: str
) -> int:

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO caption_sessions (
                discord_message_id,
                discord_channel_id,
                user_notes,
                image_urls
            )
            VALUES (?, ?, ?, ?)
        """, (
            discord_message_id,
            discord_channel_id,
            user_notes,
            image_urls
        ))

        conn.commit()

        return cursor.lastrowid


def create_version(
    session_id: int,
    caption: str,
    openai_response_id: Optional[str],
    revision_type: str
) -> CaptionVersion:

    with get_connection() as conn:

        row = conn.execute("""
            SELECT COALESCE(MAX(version_number), 0)
            FROM caption_versions
            WHERE session_id = ?
        """, (session_id,)).fetchone()

        next_version = row[0] + 1

        cursor = conn.execute("""
            INSERT INTO caption_versions (
                session_id,
                version_number,
                caption,
                openai_response_id,
                revision_type
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            next_version,
            caption,
            openai_response_id,
            revision_type
        ))

        version_id = cursor.lastrowid

        conn.commit()

        return get_version(version_id)


def get_session(
    session_id: int
) -> Optional[CaptionSession]:

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT *
            FROM caption_sessions
            WHERE id = ?
        """, (session_id,)).fetchone()

        if row is None:
            return None

        data = dict(row)

        data["is_finalized"] = bool(data["is_finalized"])

        return CaptionSession(**data)


def get_version(
    version_id: int
) -> Optional[CaptionVersion]:

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT
                id,
                session_id,
                version_number,
                caption,
                openai_response_id,
                revision_type
            FROM caption_versions
            WHERE id = ?
        """, (version_id,)).fetchone()

        if row is None:
            return None

        return CaptionVersion(**dict(row))


def get_version_by_number(
    session_id: int,
    version_number: int
) -> Optional[CaptionVersion]:

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT
                id,
                session_id,
                version_number,
                caption,
                openai_response_id,
                revision_type
            FROM caption_versions
            WHERE session_id = ?
              AND version_number = ?
        """, (
            session_id,
            version_number
        )).fetchone()

        if row is None:
            return None

        return CaptionVersion(**dict(row))


def get_latest_version(
    session_id: int
) -> Optional[CaptionVersion]:

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        row = conn.execute("""
            SELECT
                id,
                session_id,
                version_number,
                caption,
                openai_response_id,
                revision_type
            FROM caption_versions
            WHERE session_id = ?
            ORDER BY version_number DESC
            LIMIT 1
        """, (session_id,)).fetchone()

        if row is None:
            return None

        return CaptionVersion(**dict(row))


def get_version_count(
    session_id: int
) -> int:

    with get_connection() as conn:

        row = conn.execute("""
            SELECT COUNT(*)
            FROM caption_versions
            WHERE session_id = ?
        """, (session_id,)).fetchone()

        return row[0]


def finalize_version(
    session_id: int,
    version_id: int
):

    with get_connection() as conn:

        conn.execute("""
            UPDATE caption_sessions
            SET is_finalized = 1,
                approved_version_id = ?
            WHERE id = ?
        """, (
            version_id,
            session_id
        ))

        conn.commit()


def unfinalize_session(
    session_id: int
):

    with get_connection() as conn:

        conn.execute("""
            UPDATE caption_sessions
            SET is_finalized = 0,
                approved_version_id = NULL
            WHERE id = ?
        """, (session_id,))

        conn.commit()


def get_approved_captions(
    limit: int = 10
) -> list[str]:

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT cv.caption
            FROM caption_sessions cs
            JOIN caption_versions cv
                ON cs.approved_version_id = cv.id
            WHERE cs.is_finalized = 1
            ORDER BY cv.id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [row[0] for row in rows]

def set_finalized_discord_message(
    session_id: int,
    message_id: int
):

    with get_connection() as conn:

        conn.execute("""
            UPDATE caption_sessions
            SET finalized_discord_message_id = ?
            WHERE id = ?
        """, (
            message_id,
            session_id
        ))

        conn.commit()