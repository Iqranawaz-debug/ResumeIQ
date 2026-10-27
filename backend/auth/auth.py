import hashlib
import json
import os
import secrets
import tempfile
import time
from collections import deque
from utils.limits import positive_int
from pathlib import Path

# Users are persisted to a local JSON file (no database required) so
# accounts survive a server restart. Sessions stay in-memory only.
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"


def _load_users() -> dict:
    # A corrupt file must stop startup: treating it as empty would let the
    # next signup overwrite every existing account.
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Account file {DATA_FILE} is corrupt. Restore it from a backup, or remove it to start with no accounts.") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Account file {DATA_FILE} has an unexpected format.")
    return data


def _save_users() -> None:
    # Write a sibling temp file, then atomically replace, so a crash mid-write
    # leaves the previous complete file in place.
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=DATA_FILE.parent, prefix=".users-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, DATA_FILE)
    except BaseException:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
        raise


users: dict = _load_users()  # email -> {"salt": str, "password_hash": str}
sessions: dict = {}  # token -> (normalized email, monotonic expiry)
SESSION_SECONDS = positive_int("SESSION_TTL_SECONDS", 3600)
LOGIN_WINDOW = positive_int("LOGIN_WINDOW_SECONDS", 60)
LOGIN_ATTEMPTS = positive_int("LOGIN_MAX_ATTEMPTS", 10)
login_attempts: dict = {}


def normalize_email(email):
    return email.strip().lower()


def allow_login(client):
    now = time.monotonic()
    for key in list(login_attempts):
        if not login_attempts[key] or login_attempts[key][-1] <= now - LOGIN_WINDOW:
            del login_attempts[key]
    if client not in login_attempts and len(login_attempts) >= 10000:
        return False
    attempts = login_attempts.setdefault(client, deque())
    while attempts and attempts[0] <= now - LOGIN_WINDOW:
        attempts.popleft()
    if len(attempts) >= LOGIN_ATTEMPTS:
        return False
    attempts.append(now)
    return True


class AuthError(Exception):
    pass


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


def create_user(email: str, password: str, full_name: str = "", company: str = "") -> None:
    email = normalize_email(email)
    if not email or not password:
        raise AuthError("Email and password are required.")
    if email in users:
        raise AuthError("An account with that email already exists.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters long.")

    salt = secrets.token_hex(16)
    users[email] = {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "full_name": full_name.strip(),
        "company": company.strip(),
    }
    _save_users()


def verify_user(email: str, password: str) -> bool:
    user = users.get(normalize_email(email))
    if not user:
        return False
    return secrets.compare_digest(_hash_password(password, user["salt"]), user["password_hash"])


def create_session(email: str) -> str:
    token = secrets.token_hex(32)
    now = time.monotonic()
    for old in list(sessions):
        if sessions[old][1] <= now:
            del sessions[old]
    sessions[token] = (normalize_email(email), now + SESSION_SECONDS)
    return token


def get_email_from_token(token: str):
    session = sessions.get(token)
    if not session:
        return None
    if session[1] <= time.monotonic():
        sessions.pop(token, None)
        return None
    return session[0]


def destroy_session(token: str) -> None:
    sessions.pop(token, None)
