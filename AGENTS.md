# TJ: Personal Trading Journal
Single-user app. Next.js frontend, FastAPI backend, PostgreSQL, worker for schedules.
The SRS in docs/SRS.md is the source of truth. If unclear, ask before coding.

## Commands
make dev | make test | make lint | make migrate | make seed | make create-user

## Hard rules
- Money: Decimal in Python, numeric in SQL, strings in JSON. Never float.
- Time: store UTC; trading days and display use Asia/Kolkata.
- Schema changes only through Alembic migrations.
- Never log or return secrets, tokens, API keys or full Kite payloads.
- Encrypt broker secrets and notification credentials with APP_ENCRYPTION_KEY.
- Use the official kiteconnect SDK. Space Kite calls at least 1 second apart.
  Handle TokenException by marking the token expired.
- Do not place orders. Do not automate Zerodha login.
- Do not invent charge rates; read them from seed/charge_rates.json.
- Do not add dependencies without asking. Do not call third-party services from the browser.
- Matcher golden tests (SRS 12.2) are the contract. Never change expected values.
- Journal data is keyed by group_key, not trade_group.id.
- Business logic goes in services/, routers stay thin.

## Process
- One milestone per branch. Reply first with a plan and questions.
- Write tests first for matcher, charges, metrics, reminders.
- Save real Kite responses (redacted) in tests/fixtures before relying on shapes.
- Items marked VERIFY in the SRS must be confirmed, then noted in the SRS.
- Finish with: tests green, lint clean, short summary of changes and open questions.

