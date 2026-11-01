"""Operator commands. There is no sign-up page (FR-AUTH-01).

    python -m app.cli create-user
    python -m app.cli set-kite-credentials

Both prompt for secrets rather than taking them as arguments, so nothing
sensitive lands in the shell history or in a process listing.
"""

from __future__ import annotations

import getpass
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import AppUser
from app.security import EncryptionKeyError, encrypt
from app.services import auth_service, token_store

MIN_PASSWORD_LENGTH = 12


def _prompt_password(label: str) -> str:
    first = getpass.getpass(f"{label}: ")
    if len(first) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if first != getpass.getpass(f"{label} (again): "):
        raise SystemExit("Passwords do not match.")
    return first


def create_user() -> int:
    email = input("Email: ").strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Enter a valid email address.")

    session = SessionLocal()
    try:
        if auth_service.get_user_by_email(session, email) is not None:
            raise SystemExit(f"{email} already exists. Use change-password instead.")
        password = _prompt_password("Password")
        auth_service.create_user(session, email, password)
        session.commit()
    finally:
        session.close()

    print(f"Created {email}.")
    return 0


def set_kite_credentials() -> int:
    """Store the Kite API key and secret, encrypted (FR-KITE-01).

    Until Settings exists, this is how credentials get in. Values default to
    KITE_API_KEY and KITE_API_SECRET from the environment.
    """
    settings = get_settings()

    session = SessionLocal()
    try:
        user = session.execute(
            select(AppUser).order_by(AppUser.created_at).limit(1)
        ).scalar_one_or_none()
        if user is None:
            raise SystemExit("Create the owner account first: make create-user")

        api_key = input(f"Kite API key [{settings.kite_api_key or 'none'}]: ").strip()
        api_key = api_key or settings.kite_api_key
        if not api_key:
            raise SystemExit("An API key is required.")

        entered = getpass.getpass("Kite API secret (blank to use KITE_API_SECRET): ")
        api_secret = entered or settings.kite_api_secret.get_secret_value()
        if not api_secret:
            raise SystemExit("An API secret is required.")

        try:
            encrypt("probe")
        except EncryptionKeyError as exc:
            raise SystemExit(str(exc)) from exc

        token_store.save_credentials(session, user, api_key, api_secret)
        session.commit()
    finally:
        session.close()

    print("Stored Kite credentials, encrypted.")
    print(
        f"Register this redirect URL in the Kite Developer Console:\n  {settings.kite_redirect_url}"
    )
    return 0


COMMANDS = {
    "create-user": create_user,
    "set-kite-credentials": set_kite_credentials,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in COMMANDS:
        print(f"Usage: python -m app.cli [{' | '.join(COMMANDS)}]", file=sys.stderr)
        return 2
    return COMMANDS[args[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
