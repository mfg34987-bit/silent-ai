import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DB = BASE_DIR / "silent_ai_knowledge.db"


# ============================================================
# KNOWLEDGE ENGINE
# ============================================================

class KnowledgeEngine:
    """
    Local Knowledge Engine for Silent AI.

    V6.2 goals:
    - Store documents and chunks.
    - Search relevant knowledge locally.
    - Keep source metadata.
    - Support TXT / MD / JSON / HTML-like text.
    - Prepare the architecture for future embeddings/vector search.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = str(
            database_path or KNOWLEDGE_DB
        )

        self._initialize_database()

    # ========================================================
    # DATABASE
    # ========================================================

    def _connect(self):
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(self):
        connection = self._connect()

        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    language TEXT NOT NULL DEFAULT 'unknown',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(document_id)
                        REFERENCES knowledge_documents(id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_documents_category
                ON knowledge_documents(category)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                ON knowledge_chunks(document_id)
                """
            )

            # FTS5 is part of normal modern SQLite builds.
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(
                    content,
                    title,
                    category,
                    source,
                    content='knowledge_chunks',
                    content_rowid='id'
                )
                """
            )

            connection.commit()

        finally:
            connection.close()

    # ========================================================
    # TEXT NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = str(text or "")

        text = text.replace("\x00", " ")

        text = re.sub(
            r"\r\n?",
            "\n",
            text,
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Approximation only.
        # The actual provider tokenizer may differ.
        return max(
            1,
            int(len(text) / 4),
        )

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text:
            return "unknown"

        arabic = len(
            re.findall(
                r"[\u0600-\u06FF]",
                text,
            )
        )

        latin = len(
            re.findall(
                r"[A-Za-z]",
                text,
            )
        )

        if arabic > latin:
            return "ar"

        if latin > arabic:
            return "en"

        return "mixed"

    # ========================================================
    # CHUNKING
    # ========================================================

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = 1800,
        overlap: int = 250,
    ) -> list[str]:

        text = self._normalize_text(text)

        if not text:
            return []

        if overlap >= chunk_size:
            overlap = max(
                0,
                chunk_size // 5,
            )

        paragraphs = re.split(
            r"\n\s*\n",
            text,
        )

        chunks = []
        current = ""

        for paragraph in paragraphs:

            paragraph = paragraph.strip()

            if not paragraph:
                continue

            # Very large paragraphs need hard splitting.
            if len(paragraph) > chunk_size:

                if current:
                    chunks.append(
                        current.strip()
                    )
                    current = ""

                start = 0

                while start < len(paragraph):

                    end = min(
                        start + chunk_size,
                        len(paragraph),
                    )

                    piece = paragraph[
                        start:end
                    ].strip()

                    if piece:
                        chunks.append(piece)

                    if end >= len(paragraph):
                        break

                    start = max(
                        0,
                        end - overlap,
                    )

                continue

            candidate = (
                f"{current}\n\n{paragraph}"
                if current
                else paragraph
            )

            if len(candidate) <= chunk_size:
                current = candidate
                continue

            if current:
                chunks.append(
                    current.strip()
                )

            tail = (
                current[-overlap:]
                if current
                else ""
            )

            current = (
                f"{tail}\n\n{paragraph}"
            ).strip()

        if current:
            chunks.append(
                current.strip()
            )

        return [
            chunk
            for chunk in chunks
            if len(chunk.strip()) >= 20
        ]

    # ========================================================
    # DOCUMENT HASH
    # ========================================================

    @staticmethod
    def _hash_document(
        title: str,
        source: str,
        content: str,
    ) -> str:

        payload = (
            f"{title}\n"
            f"{source}\n"
            f"{content}"
        )

        return hashlib.sha256(
            payload.encode(
                "utf-8",
                errors="ignore",
            )
        ).hexdigest()

    # ========================================================
    # INGEST DOCUMENT
    # ========================================================

    def add_document(
        self,
        title: str,
        content: str,
        source: str = "local",
        category: str = "general",
        language: str | None = None,
        replace_existing: bool = False,
    ) -> dict:

        title = str(
            title or "Untitled"
        ).strip()

        source = str(
            source or "local"
        ).strip()

        category = str(
            category or "general"
        ).strip().lower()

        content = self._normalize_text(
            content
        )

        if not content:
            return {
                "status": "ignored",
                "reason": "empty_content",
            }

        if language is None:
            language = self._detect_language(
                content
            )

        content_hash = self._hash_document(
            title,
            source,
            content,
        )

        chunks = self._chunk_text(
            content
        )

        if not chunks:
            return {
                "status": "ignored",
                "reason": "no_chunks",
            }

        connection = self._connect()

        try:
            existing = connection.execute(
                """
                SELECT id
                FROM knowledge_documents
                WHERE content_hash = ?
                """,
                (content_hash,),
            ).fetchone()

            if existing and not replace_existing:
                return {
                    "status": "exists",
                    "document_id": existing["id"],
                    "chunks": 0,
                }

            if existing and replace_existing:

                document_id = existing["id"]

                connection.execute(
                    """
                    DELETE FROM knowledge_fts
                    WHERE rowid IN (
                        SELECT id
                        FROM knowledge_chunks
                        WHERE document_id = ?
                    )
                    """,
                    (document_id,),
                )

                connection.execute(
                    """
                    DELETE FROM knowledge_chunks
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )

                connection.execute(
                    """
                    UPDATE knowledge_documents
                    SET
                        title = ?,
                        source = ?,
                        category = ?,
                        language = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title,
                        source,
                        category,
                        language,
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                        document_id,
                    ),
                )

            else:

                now = datetime.now(
                    timezone.utc
                ).isoformat()

                cursor = connection.execute(
                    """
                    INSERT INTO knowledge_documents (
                        content_hash,
                        title,
                        source,
                        category,
                        language,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        content_hash,
                        title,
                        source,
                        category,
                        language,
                        now,
                        now,
                    ),
                )

                document_id = cursor.lastrowid

            for index, chunk in enumerate(
                chunks
            ):

                cursor = connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        document_id,
                        chunk_index,
                        content,
                        token_estimate,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        index,
                        chunk,
                        self._estimate_tokens(
                            chunk
                        ),
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                    ),
                )

                chunk_id = cursor.lastrowid

                connection.execute(
                    """
                    INSERT INTO knowledge_fts (
                        rowid,
                        content,
                        title,
                        category,
                        source
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        chunk,
                        title,
                        category,
                        source,
                    ),
                )

            connection.commit()

            return {
                "status": "ok",
                "document_id": document_id,
                "title": title,
                "category": category,
                "language": language,
                "chunks": len(chunks),
            }

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    # ========================================================
    # ADD FILE
    # ========================================================

    def add_text_file(
        self,
        file_path: str | Path,
        category: str = "general",
        source: str | None = None,
    ) -> dict:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                str(path)
            )

        content = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        return self.add_document(
            title=path.stem,
            content=content,
            source=source or str(path),
            category=category,
        )

    # ========================================================
    # SEARCH
    # ========================================================

    @staticmethod
    def _build_fts_query(query: str) -> str:
        words = re.findall(
            r"[\w\u0600-\u06FF]+",
            query.lower(),
        )

        words = [
            word
            for word in words
            if len(word) >= 2
        ]

        if not words:
            return ""

        # Prefix matching makes retrieval more forgiving.
        return " OR ".join(
            f'"{word}"*'
            for word in words[:20]
        )

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 8,
    ) -> list[dict]:

        query = self._normalize_text(
            query
        )

        if not query:
            return []

        fts_query = self._build_fts_query(
            query
        )

        if not fts_query:
            return []

        limit = max(
            1,
            min(
                int(limit),
                30,
            ),
        )

        connection = self._connect()

        try:

            if category:
                rows = connection.execute(
                    """
                    SELECT
                        kc.id,
                        kc.content,
                        kc.chunk_index,
                        kd.title,
                        kd.source,
                        kd.category,
                        kd.language,
                        bm25(knowledge_fts) AS score
                    FROM knowledge_fts
                    JOIN knowledge_chunks kc
                        ON kc.id = knowledge_fts.rowid
                    JOIN knowledge_documents kd
                        ON kd.id = kc.document_id
                    WHERE knowledge_fts MATCH ?
                      AND kd.category = ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (
                        fts_query,
                        category,
                        limit,
                    ),
                ).fetchall()

            else:
                rows = connection.execute(
                    """
                    SELECT
                        kc.id,
                        kc.content,
                        kc.chunk_index,
                        kd.title,
                        kd.source,
                        kd.category,
                        kd.language,
                        bm25(knowledge_fts) AS score
                    FROM knowledge_fts
                    JOIN knowledge_chunks kc
                        ON kc.id = knowledge_fts.rowid
                    JOIN knowledge_documents kd
                        ON kd.id = kc.document_id
                    WHERE knowledge_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (
                        fts_query,
                        limit,
                    ),
                ).fetchall()

            return [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "source": row["source"],
                    "category": row["category"],
                    "language": row["language"],
                    "chunk_index": row["chunk_index"],
                    "score": float(
                        row["score"]
                    ),
                    "content": row["content"],
                }
                for row in rows
            ]

        finally:
            connection.close()

    # ========================================================
    # CONTEXT BUILDER
    # ========================================================

    def build_context(
        self,
        query: str,
        category: str | None = None,
        limit: int = 6,
        max_chars: int = 18_000,
    ) -> str:

        results = self.search(
            query=query,
            category=category,
            limit=limit,
        )

        if not results:
            return ""

        blocks = []
        used = 0

        for index, item in enumerate(
            results,
            start=1,
        ):

            block = (
                f"[Knowledge {index}]\n"
                f"Title: {item['title']}\n"
                f"Category: {item['category']}\n"
                f"Source: {item['source']}\n"
                f"Content:\n{item['content']}"
            )

            if (
                used + len(block)
                > max_chars
            ):
                break

            blocks.append(block)
            used += len(block)

        return "\n\n".join(
            blocks
        )

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict:

        connection = self._connect()

        try:

            documents = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM knowledge_documents
                """
            ).fetchone()["count"]

            chunks = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM knowledge_chunks
                """
            ).fetchone()["count"]

            categories = connection.execute(
                """
                SELECT
                    category,
                    COUNT(*) AS count
                FROM knowledge_documents
                GROUP BY category
                ORDER BY count DESC
                """
            ).fetchall()

            return {
                "documents": documents,
                "chunks": chunks,
                "categories": [
                    {
                        "category": row["category"],
                        "documents": row["count"],
                    }
                    for row in categories
                ],
            }

        finally:
            connection.close()


# ============================================================
# GLOBAL INSTANCE
# ============================================================

knowledge_engine = KnowledgeEngine()