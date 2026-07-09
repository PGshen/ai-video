import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.models.user import User

PASSWORD_ITERATIONS = 210_000


@dataclass(frozen=True)
class CurrentUser:
    id: str
    username: str
    display_name: str | None
    role: str
    is_active: bool


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    return hmac.compare_digest(_b64url_encode(digest), expected)


def create_access_token(user: User | CurrentUser) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return encode_token(payload)


def encode_token(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        settings.AUTH_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token") from exc

    signing_input = f"{header_part}.{payload_part}"
    expected_signature = hmac.new(
        settings.AUTH_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_part):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_part))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Token expired")
    return payload


def current_user_from_token(token: str) -> CurrentUser:
    payload = decode_token(token)
    user_id = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")
    is_active = payload.get("is_active")
    if not isinstance(user_id, str) or not isinstance(username, str):
        raise ValueError("Invalid token payload")
    if role not in {"admin", "user"} or not isinstance(is_active, bool):
        raise ValueError("Invalid token payload")
    display_name = payload.get("display_name")
    return CurrentUser(
        id=user_id,
        username=username,
        display_name=display_name if isinstance(display_name, str) else None,
        role=role,
        is_active=is_active,
    )
