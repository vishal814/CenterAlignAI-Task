import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.DATABASE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        tier TEXT DEFAULT 'standard',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        issue TEXT NOT NULL,
        payment_id TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        status TEXT NOT NULL DEFAULT 'charged',
        refund_status TEXT NOT NULL DEFAULT 'none',
        refund_id TEXT,
        refund_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS refunds (
        id TEXT PRIMARY KEY,
        payment_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'completed',
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (payment_id) REFERENCES payments(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        payment_id TEXT NOT NULL,
        amount REAL NOT NULL,
        action TEXT NOT NULL DEFAULT 'issue_refund',
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        decision_notes TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );

    -- Simulates transient service failures for specific payments
    CREATE TABLE IF NOT EXISTS transient_failures (
        payment_id TEXT PRIMARY KEY,
        failures_remaining INTEGER NOT NULL DEFAULT 1
    );
    """)

    conn.commit()
    conn.close()
