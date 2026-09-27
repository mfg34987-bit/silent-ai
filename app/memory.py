import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


# =========================================================
# Database
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_FILE = BASE_DIR / "silent_ai.db"


def get_connection():
    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# Initialize Database
# =========================================================

def init_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (
                conversation_id
            )
            REFERENCES conversations(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_messages_conversation
        ON messages(conversation_id)
        """
    )

    connection.commit()
    connection.close()


# =========================================================
# Conversation
# =========================================================

def create_conversation(
    title: str = "محادثة جديدة",
) -> str:

    conversation_id = str(
        uuid.uuid4()
    )

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO conversations (
            id,
            title,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            title,
            now,
            now,
        ),
    )

    connection.commit()
    connection.close()

    return conversation_id


def get_conversation(
    conversation_id: str,
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id = ?
        """,
        (
            conversation_id,
        ),
    ).fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


def update_conversation_title(
    conversation_id: str,
    title: str,
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE conversations
        SET title = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            title,
            datetime.now().isoformat(
                timespec="seconds"
            ),
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def list_conversations():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM conversations
        ORDER BY updated_at DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def delete_conversation(
    conversation_id: str,
):

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM messages
        WHERE conversation_id = ?
        """,
        (
            conversation_id,
        ),
    )

    connection.execute(
        """
        DELETE FROM conversations
        WHERE id = ?
        """,
        (
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


# =========================================================
# Messages
# =========================================================

def save_message(
    conversation_id: str,
    role: str,
    content: str,
):

    connection = get_connection()

    now = datetime.now().isoformat(
        timespec="seconds"
    )

    connection.execute(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content,
            now,
        ),
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (
            now,
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def get_messages(
    conversation_id: str,
    limit: int = 30,
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            conversation_id,
            limit,
        ),
    ).fetchall()

    connection.close()

    messages = [
        dict(row)
        for row in rows
    ]

    messages.reverse()

    return messages


# =========================================================
# AI Context
# =========================================================

def build_context(
    conversation_id: str,
    limit: int = 20,
) -> str:

    messages = get_messages(
        conversation_id=conversation_id,
        limit=limit,
    )

    if not messages:
        return ""

    context_parts = []

    for message in messages:

        role = message["role"]
        content = message["content"]

        if role == "user":
            speaker = "المستخدم"
        else:
            speaker = "Silent AI"

        context_parts.append(
            f"{speaker}:\n{content}"
        )

    return "\n\n".join(
        context_parts
    )


# =========================================================
# Automatic Conversation Title
# =========================================================

def generate_conversation_title(
    message: str,
) -> str:

    title = message.strip()

    if not title:
        return "محادثة جديدة"

    title = " ".join(
        title.split()
    )

    if len(title) > 45:
        title = title[:45].rstrip() + "..."

    return title