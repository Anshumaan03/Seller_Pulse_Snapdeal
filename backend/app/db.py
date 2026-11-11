"""Tiny SQLite store for the action plan and call summaries (demo session state)."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def db_path() -> str:
    return os.environ.get("SELLERPULSE_DB", str(ROOT / "data" / "sellerpulse.db"))


@contextmanager
def conn():
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    Path(db_path()).parent.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS action_items (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   seller_id TEXT NOT NULL,
                   item_key TEXT NOT NULL,
                   payload TEXT NOT NULL,
                   created_at TEXT NOT NULL
               )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS call_summaries (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   seller_id TEXT NOT NULL,
                   payload TEXT NOT NULL,
                   created_at TEXT NOT NULL
               )"""
        )


def reset_seller(seller_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM action_items WHERE seller_id = ?", (seller_id,))
        c.execute("DELETE FROM call_summaries WHERE seller_id = ?", (seller_id,))


def save_items(seller_id: str, items: list[dict], created_at: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM action_items WHERE seller_id = ?", (seller_id,))
        for it in items:
            c.execute(
                "INSERT INTO action_items (seller_id, item_key, payload, created_at) VALUES (?,?,?,?)",
                (seller_id, it["key"], json.dumps(it), created_at),
            )


def load_items(seller_id: str) -> tuple[list[dict], str | None]:
    with conn() as c:
        rows = c.execute(
            "SELECT payload, created_at FROM action_items WHERE seller_id = ? ORDER BY id",
            (seller_id,),
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows], (rows[0]["created_at"] if rows else None)


def save_summary(seller_id: str, payload: dict, created_at: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO call_summaries (seller_id, payload, created_at) VALUES (?,?,?)",
            (seller_id, json.dumps(payload), created_at),
        )


def load_summaries(seller_id: str) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT payload FROM call_summaries WHERE seller_id = ? ORDER BY id", (seller_id,)
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows]
