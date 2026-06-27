"""
Local Q&A log. Lives on the user's machine — the model never sees it.

Stored as SQLite at ~/Library/Application Support/TextKit/history.db on
macOS, %APPDATA%\\TextKit\\history.db on Windows. Lets the user scroll
back through past answers and search them, without re-querying Claude
(so zero added API cost). Server-side memory and prompt-cached context
can layer on later; this is the cheap, useful first cut.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime


# Canned questions that get re-used for every invocation of a given hotkey.
# When the stored question matches one of these, the list label falls back
# to the answer's first line so capture entries aren't all visually identical.
_CANNED_QUESTIONS = {
    "help me with what's on my screen",
}


def default_db_path():
    """Cross-platform per-user location for the history DB."""
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/TextKit")
    elif sys.platform.startswith("win"):
        base = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), "TextKit"
        )
    else:
        base = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "textkit",
        )
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "history.db")


class HistoryEntry:
    __slots__ = ("id", "ts", "question", "answer", "model")

    def __init__(self, id, ts, question, answer, model):
        self.id = id
        self.ts = ts
        self.question = question or ""
        self.answer = answer or ""
        self.model = model or ""

    def short_label(self, max_chars=72):
        """One-line label for the list view.

        Hotkey-captured entries all carry the canned question 'Help me
        with what's on my screen' — using that as the label would make
        every capture row look identical. For canned/empty questions,
        surface the first line of the answer instead, prefixed with
        'Screen:' so capture entries are distinguishable from typed
        questions at a glance.
        """
        q = (self.question or "").strip()
        a = (self.answer or "").strip()
        when = datetime.fromtimestamp(self.ts).strftime("%b %d %H:%M")

        if (not q) or q.lower() in _CANNED_QUESTIONS:
            first_line = next((ln for ln in a.splitlines() if ln.strip()), "")
            text = f"Screen: {first_line}" if first_line else "Screen: (no response)"
        else:
            text = q.replace("\n", " ").strip()

        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        return f"{when}  —  {text}"


class HistoryStore:
    """Per-user local Q&A log.

    Single-file SQLite, append-only from the agent's perspective. Reads
    are cheap and synchronous; writes are best-effort and never block
    the request path (failure is logged and swallowed).
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        question TEXT NOT NULL DEFAULT '',
        answer TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(ts DESC);
    """

    def __init__(self, path=None):
        self.path = path or default_db_path()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init_schema()

    # SQLite connections are cheap; one-per-call avoids any threading
    # surprises with the Tk mainloop and asyncio worker threads.
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=5.0)
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self):
        with self._conn() as c:
            c.executescript(self._SCHEMA)

    def add(self, question, answer, model=""):
        """Append a Q&A. Best-effort; raises only on SQL-level errors."""
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO entries (ts, question, answer, model) "
                "VALUES (?, ?, ?, ?)",
                (int(time.time()), question or "", answer or "", model or ""),
            )
            return cur.lastrowid

    def recent(self, limit=100):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts, question, answer, model FROM entries "
                "ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            HistoryEntry(r["id"], r["ts"], r["question"], r["answer"], r["model"])
            for r in rows
        ]

    def search(self, query, limit=200):
        """Substring match on question OR answer (case-insensitive)."""
        q = (query or "").strip()
        if not q:
            return self.recent(limit)
        like = f"%{q.lower()}%"
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts, question, answer, model FROM entries "
                "WHERE LOWER(question) LIKE ? OR LOWER(answer) LIKE ? "
                "ORDER BY ts DESC LIMIT ?",
                (like, like, limit),
            ).fetchall()
        return [
            HistoryEntry(r["id"], r["ts"], r["question"], r["answer"], r["model"])
            for r in rows
        ]

    def get(self, entry_id):
        with self._conn() as c:
            row = c.execute(
                "SELECT id, ts, question, answer, model FROM entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if not row:
            return None
        return HistoryEntry(
            row["id"], row["ts"], row["question"], row["answer"], row["model"]
        )

    def count(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
