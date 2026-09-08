from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

_DB_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        settings.db_path,
        timeout=30,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init() -> None:
    with _DB_LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                first_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL CHECK(price > 0),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                telegram_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                unit_price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                total_amount INTEGER NOT NULL,
                payment_method TEXT NOT NULL,
                status TEXT NOT NULL,
                klik_signature TEXT,
                qris_url TEXT,
                direct_url TEXT,
                expired_at TEXT,
                proof_file_id TEXT,
                admin_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_telegram_id
                ON orders(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status_method
                ON orders(status, payment_method);
            """
        )
        _seed_products_if_empty(conn)


def _seed_products_if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count:
        return

    seed_path = Path("data/seed_products.json")
    if not seed_path.exists():
        return

    try:
        items = json.loads(seed_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    for item in items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        price = int(item.get("price", 0))
        if price <= 0:
            continue
        conn.execute(
            """
            INSERT INTO products(name, description, price, active, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                str(item.get("description", "")).strip(),
                price,
                1 if item.get("active", True) else 0,
                _now(),
            ),
        )


def upsert_user(user: Any) -> None:
    now = _now()
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO users(telegram_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                updated_at=excluded.updated_at
            """,
            (
                user.id,
                user.username or "",
                user.first_name or "",
                now,
                now,
            ),
        )


def products(active_only: bool = True):
    sql = "SELECT * FROM products"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY id"
    with _DB_LOCK, _connect() as conn:
        return conn.execute(sql).fetchall()


def product(product_id: int):
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE id=?",
            (product_id,),
        ).fetchone()


def add_product(name: str, description: str, price: int) -> int:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO products(name, description, price, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (name.strip(), description.strip(), int(price), _now()),
        )
        return int(cur.lastrowid)


def create_order(
    order_id: str,
    telegram_id: int,
    product_row,
    quantity: int,
    amount: int,
    payment_method: str,
) -> None:
    now = _now()
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO orders(
                order_id, telegram_id, product_id, product_name, unit_price,
                quantity, amount, total_amount, payment_method, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                order_id,
                telegram_id,
                product_row["id"],
                product_row["name"],
                product_row["price"],
                quantity,
                amount,
                amount,
                payment_method,
                now,
                now,
            ),
        )


def order(order_id: str):
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE order_id=?",
            (order_id,),
        ).fetchone()


def update_payment(
    order_id: str,
    *,
    total_amount: int | None = None,
    signature: str | None = None,
    qris_url: str | None = None,
    direct_url: str | None = None,
    expired_at: str | None = None,
    status: str | None = None,
) -> None:
    mapping = {
        "total_amount": total_amount,
        "klik_signature": signature,
        "qris_url": qris_url,
        "direct_url": direct_url,
        "expired_at": expired_at,
        "status": status,
    }
    fields: list[str] = []
    values: list[Any] = []

    for field, value in mapping.items():
        if value is not None:
            fields.append(f"{field}=?")
            values.append(value)

    if not fields:
        return

    fields.append("updated_at=?")
    values.append(_now())
    values.append(order_id)

    with _DB_LOCK, _connect() as conn:
        conn.execute(
            f"UPDATE orders SET {', '.join(fields)} WHERE order_id=?",
            values,
        )


def mark_paid_if_pending(order_id: str, note: str = "") -> bool:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE orders
            SET status='PAID', admin_note=?, updated_at=?
            WHERE order_id=? AND status='PENDING'
            """,
            (note, _now(), order_id),
        )
        return cur.rowcount == 1


def cancel(order_id: str) -> bool:
    with _DB_LOCK, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE orders
            SET status='CANCELLED', updated_at=?
            WHERE order_id=? AND status NOT IN ('PAID','CANCELLED')
            """,
            (_now(), order_id),
        )
        return cur.rowcount == 1


def add_proof(order_id: str, file_id: str) -> None:
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            UPDATE orders
            SET proof_file_id=?, updated_at=?
            WHERE order_id=?
            """,
            (file_id, _now(), order_id),
        )


def recent(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()


def latest_pending_for_user(telegram_id: int):
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM orders
            WHERE telegram_id=? AND status='PENDING'
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()


def pending_auto_orders():
    with _DB_LOCK, _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM orders
            WHERE payment_method='KLIKRIS' AND status='PENDING'
            ORDER BY id
            """
        ).fetchall()


def healthcheck() -> bool:
    try:
        with _DB_LOCK, _connect() as conn:
            return conn.execute("SELECT 1").fetchone()[0] == 1
    except sqlite3.Error:
        return False
