from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import aiosqlite

Status = Literal["open", "done"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT    NOT NULL,
    assignee_id  INTEGER,
    tags         TEXT,
    status       TEXT    NOT NULL DEFAULT 'open',
    created_by   INTEGER NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_todos_status   ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_assignee ON todos(assignee_id);
"""


@dataclass(frozen=True, slots=True)
class Todo:
    id: int
    text: str
    assignee_id: int | None
    tags: str | None
    status: Status
    created_by: int
    created_at: str
    completed_at: str | None

    @property
    def tag_list(self) -> list[str]:
        return [t for t in (self.tags or "").split(",") if t]


def _row(r: aiosqlite.Row) -> Todo:
    return Todo(
        id=r["id"],
        text=r["text"],
        assignee_id=r["assignee_id"],
        tags=r["tags"],
        status=r["status"],
        created_by=r["created_by"],
        created_at=r["created_at"],
        completed_at=r["completed_at"],
    )


def _normalize_tags(tags: str | None) -> str | None:
    if not tags:
        return None
    parts = [t.strip().lower().lstrip("#") for t in tags.split(",")]
    parts = [t for t in parts if t]
    return ",".join(parts) if parts else None


class TodoStore:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    @classmethod
    async def open(cls, path: str) -> "TodoStore":
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.executescript(SCHEMA)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

    async def add(
        self,
        text: str,
        created_by: int,
        assignee_id: int | None = None,
        tags: str | None = None,
    ) -> Todo:
        cursor = await self._conn.execute(
            "INSERT INTO todos (text, assignee_id, tags, created_by) VALUES (?, ?, ?, ?)",
            (text, assignee_id, _normalize_tags(tags), created_by),
        )
        await self._conn.commit()
        return await self.get(cursor.lastrowid)  # type: ignore[arg-type]

    async def get(self, todo_id: int) -> Todo:
        async with self._conn.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise KeyError(todo_id)
        return _row(row)

    async def list(
        self,
        status: Status | Literal["all"] = "open",
        assignee_id: int | None = None,
        tag: str | None = None,
        limit: int = 25,
    ) -> list[Todo]:
        clauses: list[str] = []
        params: list[object] = []
        if status != "all":
            clauses.append("status = ?")
            params.append(status)
        if assignee_id is not None:
            clauses.append("assignee_id = ?")
            params.append(assignee_id)
        if tag:
            clauses.append("(',' || tags || ',') LIKE ?")
            params.append(f"%,{tag.lower().lstrip('#')},%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM todos {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row(r) for r in rows]

    async def mark_done(self, todo_id: int) -> Todo:
        await self._conn.execute(
            "UPDATE todos SET status='done', completed_at=datetime('now') WHERE id=?",
            (todo_id,),
        )
        await self._conn.commit()
        return await self.get(todo_id)

    async def remove(self, todo_id: int) -> None:
        cursor = await self._conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
        await self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(todo_id)

    async def assign(self, todo_id: int, assignee_id: int) -> Todo:
        await self._conn.execute(
            "UPDATE todos SET assignee_id=? WHERE id=?", (assignee_id, todo_id)
        )
        await self._conn.commit()
        return await self.get(todo_id)
