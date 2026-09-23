"""
SQLite Database module for GdG-Help-Bot.
Manages support tickets, status updates, and admin responses.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH


@contextmanager
def get_db():
    """Context manager for SQLite database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initializes the database schema."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_full_name TEXT NOT NULL,
                username TEXT,
                question TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                admin_message_id INTEGER,
                accepted_by_id INTEGER,
                accepted_by_name TEXT,
                closed_by_id INTEGER,
                closed_by_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Ticket responses history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                admin_name TEXT NOT NULL,
                response_text TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


def create_ticket(
    user_id: int,
    user_full_name: str,
    username: Optional[str],
    question: str
) -> int:
    """Inserts a new ticket into the database and returns its ID."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickets (
                user_id, user_full_name, username, question, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'open', ?, ?)
        """, (user_id, user_full_name, username, question, now, now))
        conn.commit()
        return cursor.lastrowid


def set_ticket_admin_message_id(ticket_id: int, admin_message_id: int):
    """Associates the sent Telegram message in the admin chat with the ticket."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets
            SET admin_message_id = ?, updated_at = ?
            WHERE id = ?
        """, (admin_message_id, now, ticket_id))
        conn.commit()


def get_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a ticket by its ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_ticket_by_admin_message_id(admin_message_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a ticket by its message ID in the admin chat."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE admin_message_id = ?", (admin_message_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_ticket_status(
    ticket_id: int,
    status: str,
    admin_id: Optional[int] = None,
    admin_name: Optional[str] = None
) -> bool:
    """
    Updates the status of a ticket ('open', 'accepted', 'closed').
    Tracks who accepted or closed it.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()

        if status == "accepted":
            cursor.execute("""
                UPDATE tickets
                SET status = ?, accepted_by_id = ?, accepted_by_name = ?, updated_at = ?
                WHERE id = ?
            """, (status, admin_id, admin_name, now, ticket_id))
        elif status == "closed":
            cursor.execute("""
                UPDATE tickets
                SET status = ?, closed_by_id = ?, closed_by_name = ?, updated_at = ?
                WHERE id = ?
            """, (status, admin_id, admin_name, now, ticket_id))
        elif status == "open":
            cursor.execute("""
                UPDATE tickets
                SET status = ?, closed_by_id = NULL, closed_by_name = NULL, updated_at = ?
                WHERE id = ?
            """, (status, now, ticket_id))
        else:
            cursor.execute("""
                UPDATE tickets
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, now, ticket_id))

        conn.commit()
        return cursor.rowcount > 0


def add_ticket_response(
    ticket_id: int,
    admin_id: int,
    admin_name: str,
    response_text: str
):
    """Records an admin response in the database."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ticket_responses (ticket_id, admin_id, admin_name, response_text, sent_at)
            VALUES (?, ?, ?, ?, ?)
        """, (ticket_id, admin_id, admin_name, response_text, now))
        cursor.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
        conn.commit()


def get_ticket_responses(ticket_id: int) -> List[Dict[str, Any]]:
    """Returns all admin responses for a ticket."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ticket_responses
            WHERE ticket_id = ?
            ORDER BY id ASC
        """, (ticket_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_user_tickets(user_id: int) -> List[Dict[str, Any]]:
    """Returns all tickets submitted by a specific user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

