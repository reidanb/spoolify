import os
import secrets
import sqlite3

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATA_DIR = os.environ.get("SPOOLIFY_DATA_DIR", "data")
AUTH_DB_PATH = os.path.join(DATA_DIR, "auth.db")
SESSION_COOKIE = "spoolify_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 days


def _secret_key() -> str:
    env = os.environ.get("SPOOLIFY_SECRET_KEY", "").strip()
    if env:
        return env
    key_path = os.path.join(DATA_DIR, ".secret_key")
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.isfile(key_path):
        with open(key_path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)
    return key


def _auth_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def user_count() -> int:
    conn = _auth_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def create_user(username: str, password: str) -> bool:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = _auth_conn()
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pw_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def user_exists(username: str) -> bool:
    conn = _auth_conn()
    row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row is not None


def reset_password(username: str, new_password: str) -> bool:
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = _auth_conn()
    cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pw_hash, username))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def verify_user(username: str, password: str) -> bool:
    conn = _auth_conn()
    row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


def make_session_token(username: str) -> str:
    s = URLSafeTimedSerializer(_secret_key())
    return s.dumps(username, salt="session")


def verify_session_token(token: str) -> str | None:
    s = URLSafeTimedSerializer(_secret_key())
    try:
        return s.loads(token, salt="session", max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
