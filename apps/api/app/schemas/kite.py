"""Request and response models for FR-KITE.

No model here carries the API secret or the access token. The API key is only
ever shown masked to its last 4 characters (FR-KITE-01).
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel

KiteStatus = Literal["connected", "expired", "not_configured", "error"]


class LoginUrlOut(BaseModel):
    login_url: str
    # Shown in Settings so it can be registered in the Kite Developer Console.
    redirect_url: str


class KiteStatusOut(BaseModel):
    status: KiteStatus
    kite_user_id: str | None = None
    api_key_masked: str | None = None
    token_issued_at: dt.datetime | None = None
    # An estimate only; the live profile() call is the real answer (FR-KITE-04).
    token_valid_until: dt.datetime | None = None
    message: str | None = None
