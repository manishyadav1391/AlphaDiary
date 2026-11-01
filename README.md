# TJ — Personal Trading Journal

A private trading journal for one Indian intraday trader. It pulls the day's
fills from Zerodha, matches them into trades, works out the real charges, and
gives you somewhere to record why you took each one.

Single user. Self-hosted. No market data, no order placement, no third party
ever sees your trades.

The specification in [`docs/SRS.md`](docs/SRS.md) is the source of truth. If
something here disagrees with it, the SRS wins.

---

## What works today

| Area | State |
|---|---|
| App login, sessions, lockout | Built |
| Zerodha connect, token storage, status | Built |
| Daily sync, idempotent ingestion | Built |
| FIFO matcher, 13 golden scenarios | Built |
| Charges engine, 8 segments, effective-dated rates | Built |
| Console tradebook import | Built |
| Trade log, trade detail, journal, tags | Built |
| Dashboard: KPIs, calendar, equity curve | Built |
| Daily playbook: plan and review | Built |
| Background worker, login reminders by email | Built |
| Deployment assets: Caddy, bootstrap, systemd | Built, **not yet run on a real host** |
| Analytics pages | Not built |
| Settings UI | Not built |
| Screenshots | Presigner built; upload flow not wired up |
| Telegram and WhatsApp reminders | Not built |
| Backup and restore scripts | Not built |

Day-to-day usage is covered in the [user manual](docs/MANUAL.md).

---

## Architecture

```
 Browser
    |  HTTPS (Caddy)
    v
 Next.js web  --/api proxy-->  FastAPI api  <--->  PostgreSQL
                                   |  ^                 ^
                                   |  |                 |
                                   v  |            Worker (one replica)
                           Kite Connect API    - 15:45 scheduled sync
                           (Zerodha)           - reminder tick, every 60 s
                                   |           - heartbeat ping
                                   v
                     S3-compatible storage (screenshots)
                                   |
                                   v
                            Resend (email)
```

The browser never calls Zerodha, S3 or Resend directly. `/api/*` is proxied
through Next.js so the session cookie stays same-origin; in production Caddy
does the same thing.

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 on the
back end. Next.js 16 (App Router), TypeScript strict, Tailwind v4, TanStack
Query, Recharts on the front.

---

## Running it locally

**You need:** Docker Desktop, Node 20+, and a Zerodha Kite Connect app.

```bash
cp .env.example .env
```

Fill in `.env`. The three that matter before anything will start:

```bash
# A real Fernet key. Everything encrypted is unreadable without it, so keep
# a copy with your backups.
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

| Variable | Set it to |
|---|---|
| `APP_ENCRYPTION_KEY` | the Fernet key printed above |
| `APP_SECRET_KEY` | any long random string |
| `POSTGRES_PASSWORD` | any password; must match `DATABASE_URL` |
| `PUBLIC_BASE_URL` | `http://localhost:3000` for local work |

Then:

```bash
make dev           # Postgres + API
make migrate       # create the schema
make seed          # charge rates, strategies, tags, reminder slots
make instruments   # 110,000 instruments from Kite (public, no token needed)
make holidays      # NSE trading calendar
make create-user   # your login

cd apps/web && npm install && npm run dev
```

Open <http://localhost:3000>.

> **`PUBLIC_BASE_URL` decides whether the session cookie is `Secure`.** Set to
> an `https://` URL while you develop over plain HTTP and the browser silently
> drops the cookie, so every request 401s and login appears to do nothing.
>
> **Changing `.env` needs `docker compose up -d`, not `restart`.** `restart`
> does not re-read `env_file`.

---

## Commands

Run through `make`, or `.\make.ps1 <target>` on Windows without GNU Make.

| Command | What it does |
|---|---|
| `make dev` | Build and start Postgres and the API |
| `make down` | Stop everything |
| `make logs` | Follow the API log |
| `make worker-logs` | Follow the worker log |
| `make shell` | A shell inside the API container |
| `make migrate` | Apply migrations. Safe to re-run |
| `make migrate-check` | Fail if models and migrations have drifted apart |
| `make revision m="..."` | Autogenerate a migration |
| `make test` | pytest, against a separate `tj_test` database |
| `make lint` | ruff, ruff format, mypy, eslint |
| `make fmt` | ruff format and autofix |
| `make seed` | Charge rates, strategies, mistake tags, reminder slots |
| `make instruments` | Refresh the Kite instruments master |
| `make holidays` | Refresh the NSE trading calendar |
| `make create-user` | Create the owner account (prompts) |
| `make kite-credentials` | Store the Kite API key and secret, encrypted |

One more, not in the Makefile:

```bash
docker compose -f docker-compose.dev.yml exec api python -m app.cli notify-test
```

Sends a test email on every enabled channel.

---

## Layout

```
apps/
  api/
    app/
      main.py config.py db.py deps.py security.py errors.py
      worker.py            background loop: sync, reminders, heartbeat
      cli.py               operator commands
      routers/             thin: auth, kite, sync, trades, dashboard,
                           playbook, importer, health
      services/            all the logic lives here
        matcher.py         FIFO matching (SRS 7.2)
        charges.py         charges engine (SRS 7.3)
        analytics.py       metric definitions (SRS 7.4)
        reminders.py       reminder slots (SRS 7.5)
        kite_client.py     the only module that talks to Zerodha
        importer.py        Console tradebook
        holidays.py        NSE calendar
        storage.py         S3 presigning
      models/ schemas/
    alembic/               migrations
    tests/                 unit/, integration/, fixtures/
  web/
    app/                   routes
    components/            shell, dashboard, trades, playbook, ui
    lib/format.ts          every number on screen goes through here
    lib/api.ts lib/queries.ts
infra/                     Caddyfile, bootstrap.sh, tj.service
seed/                      charge_rates, journal_seeds, market_holidays
docs/                      SRS, DESIGN, SCREENS, MANUAL
```

---

## Rules that are not negotiable

These are enforced by tests and will be rejected in review. Full list in
[`AGENTS.md`](AGENTS.md).

- **Money is `Decimal` in Python, `numeric` in SQL, and a plain string in
  JSON.** Never `float`. JSON numbers are doubles; routing money through one
  undoes the whole pipeline. A test asserts no `Float` column exists.
- **Times are stored UTC.** Trading days and anything displayed use
  Asia/Kolkata. Kite sends IST wall clock with no offset, so a naive datetime
  must never reach the database.
- **Schema changes go through Alembic.** `make migrate-check` must stay clean.
- **Journal data is keyed by `group_key`, not `trade_group.id`.** The id is a
  fresh UUID every time the matcher rebuilds; notes keyed to it would vanish
  on the next sync.
- **Never log or return a secret**, a token, an API key or a full Kite payload.
- **Charge rates are never invented.** They live in `seed/charge_rates.json`,
  transcribed from Zerodha's published page.
- **The golden matcher scenarios (SRS 12.2) are the contract.** Expected
  values do not change without the owner's approval.
- **Business logic goes in `services/`.** Routers stay thin.

---

## Tests

```bash
make test
```

351 tests. They run against a **separate `tj_test` database** that the suite
creates and migrates itself, with a guard that refuses to run anywhere whose
name does not end in `_test` — the development database holds real broker
credentials and real trades.

Worth knowing what some of them pin down:

- `tests/unit/test_matcher.py` — all 13 golden scenarios from SRS 12.2,
  verbatim.
- `tests/unit/test_charges.py` — two worked orders against the shipped rate
  set, as a regression lock. If a rate moves, these fail on purpose.
- `tests/unit/test_reminders.py` — the six FR-REM acceptance cases, all with
  an injected clock.
- `tests/unit/test_analytics.py` — the worked example from SRS 7.4.

---

## Deploying

`infra/bootstrap.sh` prepares an Ubuntu 24.04 host: swap, Docker, firewall,
log rotation, systemd. `docker-compose.yml` is the production stack, pulling
tagged images rather than building on the server. `infra/Caddyfile` terminates
TLS and routes `/api/*` to the API and everything else to the web app.

It has been syntax-checked but **not run on a real host**. The full procedure
is in SRS §11.2, and `docs/RUNBOOK.md` is still to be written.

---

## Documentation

| File | For |
|---|---|
| [`docs/SRS.md`](docs/SRS.md) | The specification. Source of truth |
| [`docs/MANUAL.md`](docs/MANUAL.md) | Using the app day to day |
| [`docs/DESIGN.md`](docs/DESIGN.md) | The design system. Read before any UI work |
| [`docs/SCREENS.md`](docs/SCREENS.md) | Screen layouts and behaviour |
| [`AGENTS.md`](AGENTS.md) | Rules for AI assistants working in this repo |
