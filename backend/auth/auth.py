import hashlib
import json
import secrets
from pathlib import Path

# Users are persisted to a local JSON file (no database required) so
# accounts survive a server restart. Sessions stay in-memory only.
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"


def _load_users() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


users: dict = _load_users()  # email -> {"salt": str, "password_hash": str}
sessions: dict = {}  # token -> email


class AuthError(Exception):
    pass


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


def create_user(email: str, password: str) -> None:
    email = email.strip().lower()
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
    }
    _save_users()


def verify_user(email: str, password: str) -> bool:
    user = users.get(email.strip().lower())
    if not user:
        return False
    return _hash_password(password, user["salt"]) == user["password_hash"]


def create_session(email: str) -> str:
    token = secrets.token_hex(32)
    sessions[token] = email
    return token


def get_email_from_token(token: str):
    return sessions.get(token)


def destroy_session(token: str) -> None:
    sessions.pop(token, None)
