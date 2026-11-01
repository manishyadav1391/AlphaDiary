"""Password hashing, session identifiers and secret encryption.

Nothing in this module logs or returns a plaintext secret. `encrypt` and
`decrypt` are the only path to the `*_enc` columns (SRS 4.3; NFR-04).
"""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

# argon2-cffi defaults to Argon2id, which is what FR-AUTH-02 requires.
_hasher = PasswordHasher()


class EncryptionKeyError(RuntimeError):
    """APP_ENCRYPTION_KEY is missing or is not a valid Fernet key."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def new_state_token() -> str:
    return secrets.token_urlsafe(32)


def _fernet() -> Fernet:
    key = get_settings().app_encryption_key.get_secret_value()
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise EncryptionKeyError(
            "APP_ENCRYPTION_KEY is not a valid Fernet key. "
            "Generate one with: python -c "
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode()
    except InvalidToken as exc:
        raise EncryptionKeyError(
            "Stored ciphertext could not be decrypted. "
            "APP_ENCRYPTION_KEY has probably changed since it was written."
        ) from exc
