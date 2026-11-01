"""Operator commands. There is no sign-up page (FR-AUTH-01).

    python -m app.cli create-user
    python -m app.cli set-kite-credentials

Both prompt for secrets rather than taking them as arguments, so nothing
sensitive lands in the shell history or in a process listing.
"""

from __future__ import annotations

import datetime as dt
import getpass
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import AppUser, ChargeRateSet, Strategy, Tag
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


def _seed_journal_lists(path: Path) -> None:
    """Default strategies and mistake tags (FR-JRN-03, FR-JRN-04).

    Insert-only: a name that already exists is left alone, so renaming one in
    Settings is not undone by the next `make seed`.
    """
    if not path.exists():
        print(f"Skipped journal seeds: {path} not found")
        return

    config = json.loads(path.read_text(encoding="utf-8"))
    session = SessionLocal()
    try:
        existing_strategies = set(session.execute(select(Strategy.name)).scalars())
        added = 0
        for name in config.get("strategies", []):
            if name not in existing_strategies:
                session.add(Strategy(name=name))
                added += 1

        existing_tags = set(session.execute(select(Tag.kind, Tag.name)).all())
        for name in config.get("mistake_tags", []):
            if ("mistake", name) not in existing_tags:
                session.add(Tag(kind="mistake", name=name))
                added += 1
        session.commit()
    finally:
        session.close()
    print(f"Seeded {added} strategies and tags.")


def seed() -> int:
    """Load seed/charge_rates.json into charge_rate_set (FR-CHG-07).

    Re-running replaces the set with the same effective_from, so correcting a
    rate is an edit to the file plus `make seed`, not a manual SQL change.
    """
    settings = get_settings()
    path = Path(settings.seed_dir) / "charge_rates.json"
    if not path.exists():
        raise SystemExit(f"Not found: {path}")

    config = json.loads(path.read_text(encoding="utf-8"))
    effective_from = dt.date.fromisoformat(config["effective_from"])
    label = str(config.get("label") or path.name)

    session = SessionLocal()
    try:
        existing = (
            session.execute(
                select(ChargeRateSet).where(ChargeRateSet.effective_from == effective_from)
            )
            .scalars()
            .all()
        )
        for row in existing:
            session.delete(row)
        session.flush()
        session.add(ChargeRateSet(effective_from=effective_from, label=label, config=config))
        session.commit()
    finally:
        session.close()

    _seed_journal_lists(Path(settings.seed_dir) / "journal_seeds.json")

    print(f"Loaded charge rates effective {effective_from}: {label}")
    for note in config.get("_source", {}).get("known_gaps", []):
        print(f"  gap: {note}")
    return 0


def load_instruments() -> int:
    """Download the Kite instruments dump and upsert it (FR-IMP-05, V4).

    The dump is served without authentication, so this works before the
    broker is connected, which a history import needs.
    """
    from app.services import instruments

    print(f"Downloading {instruments.PUBLIC_DUMP_URL} ...")
    text = instruments.fetch_dump()

    session = SessionLocal()
    try:
        written = instruments.load_dump(session, text)
        session.commit()
        total = instruments.count(session)
    finally:
        session.close()

    print(f"Upserted {written} instruments; {total} now stored.")
    print("Note: the dump carries lot_size but not multiplier, so VERIFY V6 stays open.")
    return 0


COMMANDS = {
    "create-user": create_user,
    "set-kite-credentials": set_kite_credentials,
    "seed": seed,
    "instruments": load_instruments,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] not in COMMANDS:
        print(f"Usage: python -m app.cli [{' | '.join(COMMANDS)}]", file=sys.stderr)
        return 2
    return COMMANDS[args[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
