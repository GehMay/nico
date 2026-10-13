import sqlite3

from config import DB_PATH
from crypto_utils import decrypt_text, encrypt_text


def open_database():
    return sqlite3.connect(DB_PATH)


def create_table():
    connection = open_database()
    connection.execute("""CREATE TABLE IF NOT EXISTS conversation(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_text TEXT,
    assistant_text TEXT
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS reminders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_text TEXT,
    due_at TEXT,
    notified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    connection.commit()
    connection.close()


def save_conversation(user_text, assistant_text):
    connection = open_database()
    connection.execute(
        "INSERT INTO conversation (user_text, assistant_text) VALUES (?, ?)",
        (encrypt_text(user_text), encrypt_text(assistant_text))
    )
    connection.commit()
    connection.close()


def fetch_all_conversations():
    connection = open_database()
    cursor = connection.execute("SELECT user_text, assistant_text FROM conversation")
    rows = cursor.fetchall()
    connection.close()
    return [(decrypt_text(user_text), decrypt_text(assistant_text)) for user_text, assistant_text in rows]


def save_fact(fact_text):
    connection = open_database()
    connection.execute(
        "INSERT INTO facts (fact_text) VALUES (?)",
        (encrypt_text(fact_text),)
    )
    connection.commit()
    connection.close()


def fetch_all_facts():
    connection = open_database()
    cursor = connection.execute("SELECT fact_text, created_at FROM facts ORDER BY id DESC")
    rows = cursor.fetchall()
    connection.close()
    return [(decrypt_text(fact_text), created_at) for fact_text, created_at in rows]


def save_reminder(reminder_text, due_at_iso):
    connection = open_database()
    connection.execute(
        "INSERT INTO reminders (reminder_text, due_at) VALUES (?, ?)",
        (encrypt_text(reminder_text), due_at_iso)
    )
    connection.commit()
    connection.close()


def fetch_due_reminders(now_iso):
    connection = open_database()
    cursor = connection.execute(
        "SELECT id, reminder_text FROM reminders WHERE notified = 0 AND due_at <= ?",
        (now_iso,)
    )
    rows = cursor.fetchall()
    connection.close()
    return [(reminder_id, decrypt_text(reminder_text)) for reminder_id, reminder_text in rows]


def fetch_reminders_between(start_iso, end_iso):
    connection = open_database()
    cursor = connection.execute(
        "SELECT reminder_text, due_at FROM reminders WHERE due_at >= ? AND due_at < ? ORDER BY due_at",
        (start_iso, end_iso)
    )
    rows = cursor.fetchall()
    connection.close()
    return [(decrypt_text(reminder_text), due_at) for reminder_text, due_at in rows]


def mark_reminder_notified(reminder_id):
    connection = open_database()
    connection.execute(
        "UPDATE reminders SET notified = 1 WHERE id = ?",
        (reminder_id,)
    )
    connection.commit()
    connection.close()
