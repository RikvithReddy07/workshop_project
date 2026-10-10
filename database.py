"""
Database management module for Appointment Booking System.
Handles SQLite connection, schema initialization, constraints, transactions,
and query execution with parameterized queries.
"""

import os
import sqlite3
import hashlib
import secrets
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appointments.db")

# Predefined standard business working hours
WORKING_TIME_SLOTS = [
    "09:00 AM - 10:00 AM",
    "10:00 AM - 11:00 AM",
    "11:00 AM - 12:00 PM",
    "12:00 PM - 01:00 PM",
    "02:00 PM - 03:00 PM",
    "03:00 PM - 04:00 PM",
    "04:00 PM - 05:00 PM"
]

def get_db_path():
    """Return the configured database path."""
    return os.environ.get("APPOINTMENTS_DB_PATH", DEFAULT_DB_PATH)

def get_db_connection():
    """Create and return a thread-safe connection with row factory."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_cancellation_token(token: str) -> str:
    """Securely hash a cancellation token with SHA-256."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

def generate_cancellation_token() -> str:
    """Generate a high-entropy URL-safe cancellation token."""
    return secrets.token_urlsafe(32)

def init_db():
    """
    Initialize SQLite tables and indexes.
    Enforces uniqueness for active bookings (status = 'Booked') using a partial unique index.
    """
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    time_slot TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Booked' CHECK(status IN ('Booked', 'Cancelled')),
                    cancellation_token_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Partial Unique Index:
            # Guarantees that only ONE active ('Booked') appointment can exist
            # for any combination of appointment_date and time_slot.
            # Cancelled appointments do not trigger collisions.
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_booking
                ON appointments(appointment_date, time_slot)
                WHERE status = 'Booked';
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_appointments_email
                ON appointments(email);
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_appointments_date
                ON appointments(appointment_date);
            """)
    finally:
        conn.close()

def get_booked_slots_for_date(appointment_date: str) -> list[str]:
    """Retrieve all active ('Booked') slots for a specific date."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT time_slot FROM appointments
            WHERE appointment_date = ? AND status = 'Booked'
            """,
            (appointment_date,)
        )
        rows = cursor.fetchall()
        return [row["time_slot"] for row in rows]
    finally:
        conn.close()

def get_available_slots_for_date(appointment_date: str) -> dict:
    """
    Returns available, booked, and all predefined slots for a given date.
    """
    booked_slots = set(get_booked_slots_for_date(appointment_date))
    available_slots = [s for s in WORKING_TIME_SLOTS if s not in booked_slots]
    return {
        "date": appointment_date,
        "all_slots": WORKING_TIME_SLOTS,
        "available_slots": available_slots,
        "booked_slots": list(booked_slots)
    }

def book_appointment(full_name: str, email: str, phone: str,
                     appointment_date: str, time_slot: str, reason: str):
    """
    Atomically insert a new appointment into the database.
    Returns:
        (appointment_id, raw_cancellation_token, None) on success
        (None, None, error_message) on failure
    """
    if time_slot not in WORKING_TIME_SLOTS:
        return None, None, f"Invalid time slot: {time_slot}. Must be during working hours."

    raw_token = generate_cancellation_token()
    token_hash = hash_cancellation_token(raw_token)

    conn = get_db_connection()
    try:
        # Use BEGIN IMMEDIATE to prevent concurrent race condition checks
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        # Check existing active booking explicitly
        cursor.execute(
            """
            SELECT id FROM appointments
            WHERE appointment_date = ? AND time_slot = ? AND status = 'Booked'
            """,
            (appointment_date, time_slot)
        )
        if cursor.fetchone():
            conn.execute("ROLLBACK")
            return None, None, "This time slot is already booked. Please select another time."

        cursor.execute(
            """
            INSERT INTO appointments (
                full_name, email, phone, appointment_date, time_slot, reason, status, cancellation_token_hash
            ) VALUES (?, ?, ?, ?, ?, ?, 'Booked', ?)
            """,
            (full_name.strip(), email.strip().lower(), phone.strip(),
             appointment_date, time_slot, reason.strip(), token_hash)
        )
        new_id = cursor.lastrowid
        conn.execute("COMMIT")
        return new_id, raw_token, None

    except sqlite3.IntegrityError:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return None, None, "This time slot is already booked. Please select another time."
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return None, None, f"Database error: {str(e)}"
    finally:
        conn.close()

def get_appointment_by_id(appointment_id: int):
    """Fetch an appointment by its ID."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_appointments(email: str = None, appointment_date: str = None, status: str = None) -> list[dict]:
    """
    Search and filter appointments by email, date, or status.
    Returns list of appointment dicts ordered by date and time descending.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT id, full_name, email, phone, appointment_date, time_slot, reason, status, created_at FROM appointments WHERE 1=1"
        params = []

        if email:
            query += " AND LOWER(email) = LOWER(?)"
            params.append(email.strip())

        if appointment_date:
            query += " AND appointment_date = ?"
            params.append(appointment_date.strip())

        if status and status.lower() != "all":
            query += " AND status = ?"
            params.append(status.strip())

        query += " ORDER BY appointment_date DESC, time_slot ASC, id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def cancel_appointment(appointment_id: int, cancellation_token: str):
    """
    Securely cancels an appointment if the provided cancellation_token matches.
    Returns:
        (True, success_message) on success
        (False, error_message) on failure
    """
    if not cancellation_token or not cancellation_token.strip():
        return False, "Cancellation token is required to cancel this appointment."

    provided_hash = hash_cancellation_token(cancellation_token)

    conn = get_db_connection()
    try:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, status, cancellation_token_hash FROM appointments WHERE id = ?",
            (appointment_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.execute("ROLLBACK")
            return False, "Appointment not found."

        if row["status"] == "Cancelled":
            conn.execute("ROLLBACK")
            return False, "This appointment has already been cancelled."

        # Verify token hash securely
        if not secrets.compare_digest(row["cancellation_token_hash"], provided_hash):
            conn.execute("ROLLBACK")
            return False, "Invalid cancellation token. Unauthorized cancellation attempt."

        cursor.execute(
            "UPDATE appointments SET status = 'Cancelled' WHERE id = ?",
            (appointment_id,)
        )
        conn.execute("COMMIT")
        return True, "Appointment cancelled successfully. The slot is now available for booking."
    except Exception as e:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, f"Database error during cancellation: {str(e)}"
    finally:
        conn.close()

def seed_sample_data():
    """Seed initial sample appointments if database is empty."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM appointments")
        count = cursor.fetchone()["count"]
        if count == 0:
            today_str = datetime.now().strftime("%Y-%m-%d")
            # Seed 2 sample appointments for today or upcoming
            book_appointment(
                full_name="Sarah Jenkins",
                email="sarah.jenkins@example.com",
                phone="+1 (555) 234-5678",
                appointment_date=today_str,
                time_slot="10:00 AM - 11:00 AM",
                reason="Routine consultation and project review"
            )
            book_appointment(
                full_name="Alex Rivera",
                email="alex.rivera@example.com",
                phone="+1 (555) 987-6543",
                appointment_date=today_str,
                time_slot="02:00 PM - 03:00 PM",
                reason="Initial strategy planning session"
            )
    finally:
        conn.close()
