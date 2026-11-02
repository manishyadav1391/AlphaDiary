# Software Requirements Specification: Personal Trading Journal (TJ)

*Version 1.0 · 1 November 2026 · Owner: single user (trader and developer) · Readers: the developer and AI coding assistants*

## 0. How to use this SRS (vibe-coding guide)

This SRS is written so that an AI coding assistant can build the app milestone by milestone without guessing. Every requirement has an ID (for example FR-SYNC-03) and, where it matters, acceptance criteria.

**Working rules**

1. **Build in milestones** (section 13), one branch per milestone. Give the assistant: the rules file in Appendix A, the sections the milestone names, and its acceptance criteria.
2. **Never let the AI guess Zerodha payloads.** Capture real, redacted sample responses into `tests/fixtures/` first, then code against them.
3. **Tests before logic** for the matcher (FR-MATCH) and the charges engine (FR-CHG). The golden scenarios in section 12 are the contract.
4. **Items marked VERIFY** (section 3.5) must be confirmed against the Kite docs, a real response or Zerodha Console before the code depends on them.
5. **If the SRS is ambiguous, ask the owner and update the SRS.** If the AI and the SRS disagree, the SRS wins.
6. **No new dependencies** without asking, and no feature that is not in this document.

**Prompt template for each milestone**

```
Read AGENTS.md and SRS sections <list>.
Implement milestone <Mn: title>.
Requirements: <IDs>.
Constraints: money is Decimal, times are UTC in storage and IST in display,
no new dependencies, no secrets in logs.
Done when: the acceptance criteria pass and `make test` is green.
First reply with a short plan and any questions; do not write code yet.
```

## 1. Introduction

### 1.1 Purpose

TJ is a private web application that imports my Zerodha trades through the free Kite Connect Personal API, converts raw fills into complete trades with accurate net P&L, and helps me improve through tagging, notes, screenshots, analytics, a daily playbook and reminders that make sure the daily import actually happens.

### 1.2 Scope

**In scope (version 1)**

- Zerodha login (one click per day), daily and manual trade sync, CSV import for history.
- Intraday-first trade matching for equity, F&O, commodities and currency instruments.
- Charges engine and net P&L.
- Dashboard, trade log, trade journal, analytics, daily playbook, settings.
- **Reminders by email, and optionally WhatsApp or Telegram, when I have not logged in to Zerodha in time for the daily sync.**
- Benchmark overlay from public daily closing values.

**Out of scope (version 1)**

- Placing, modifying or cancelling orders.
- Live prices, live charts, alerts on prices, automatic strategy detection from candles.
- Multiple users, public sign-up, billing, mobile native apps.
- Tax filing outputs.

### 1.3 Definitions

| Term | Meaning |
| --- | --- |
| Fill | One execution reported by Zerodha (a row of the trades endpoint). Several fills can belong to one order. |
| Order | An instruction I placed. It can be executed in many fills. |
| Trade (trade group) | A sequence of fills from a flat position to flat again in one instrument and product. This is the unit I tag and review. |
| MIS / NRML / CNC | Zerodha product types: MIS is intraday margin, NRML is normal F&O and commodity carry, CNC is equity delivery. |
| R-multiple | Net P&L divided by planned risk. |
| IST | India Standard Time, UTC+05:30. All trading days follow IST. |
| FY | Indian financial year, 1 April to 31 March. |
| Token | The Kite access token, valid for one trading day (expires around 6:00 AM IST next day). |
| Sync | Fetching orders, trades and positions from Kite and storing them. |

### 1.4 References

- Kite Connect v3 documentation: https://kite.trade/docs/connect/v3/
- Zerodha Console (tradebook and P&L reports) and the Zerodha brokerage calculator, used to reconcile.
- Python SDK: `kiteconnect` (official).

## 2. Decisions already made by the owner

| # | Question | Decision |
| --- | --- | --- |
| 1 | Which trading style first? | **Intraday.** Version 1 defaults every screen to intraday trades (opened and closed on the same IST day). The matcher is generic, so a position carried overnight is simply an open trade that closes later. |
| 2 | Which instruments? | **All:** NSE and BSE equity, NFO and BFO derivatives, MCX commodities, CDS and BCD currency. |
| 3 | Hosting? | AWS account created after 15 July 2025, so it is on the **Free Plan** (credits and a 6-month limit). Use a free-tier-eligible t3.small in Mumbai. Before the plan ends, upgrade or migrate (section 11). |
| 4 | How much history to import? | Options below. **Recommended: option B.** |
| 5 | Benchmark overlay? | **Yes**, using public daily closes (Nifty 50 and Bank Nifty), optional and best-effort. |
| 6 | New: reminders | Send a **daily reminder by email, and optionally WhatsApp or Telegram**, if I have not logged in to Zerodha, because the sync needs a valid token before 3:45 PM IST. |

**History import timeline options**

| Option | Range | Good for | Trade-off |
| --- | --- | --- | --- |
| A. Minimal | Last 30 days | Fast start, tiny import | Little data for analytics |
| **B. Recommended** | **From 1 April 2026 (current FY)** | Enough sample size, matches Console’s financial-year reports so reconciliation is easy | About 7 months of CSV files to import |
| C. Two years | From 1 April 2025 | Bigger sample, year-over-year comparison | Needs charge rates that applied in earlier periods; more reconciliation work |
| D. Custom | From my first trade date | Complete history | Most effort; rate changes over time matter |

Regardless of option, the import must be repeatable and idempotent (FR-IMP-03), and charge rates carry effective dates (FR-CHG-02). VERIFY how many months Console allows per tradebook export.

## 3. Overall description

### 3.1 Product perspective

```
 Browser (me)
    |  HTTPS (Caddy)
    v
 Next.js web  --/api proxy-->  FastAPI api  <--->  PostgreSQL
                                  |  ^                    ^
                                  |  |                    |
                                  v  |              Worker (scheduler)
                          Kite Connect API     - 3:45 PM sync
                          (Zerodha)            - reminder ticks every minute
                                               - nightly backup, benchmark fetch
                                  |
                                  v
                    Object storage (S3 API): screenshots, backups
                                  |
                                  v
                  Email (SMTP) / WhatsApp Cloud API / Telegram Bot
```

### 3.2 Users

One user: the owner. No roles. The app must still require a login because it holds financial data and broker credentials.

### 3.3 Operating environment

- Server: Linux VM running Docker Compose.
- Client: current Chrome, Edge, Safari or Firefox on laptop and phone (responsive layout).
- Time zone of all business logic: Asia/Kolkata.

### 3.4 Constraints from the free Kite Connect Personal plan

| Constraint | Consequence in this design |
| --- | --- |
| No market data, no WebSocket | No auto-detected setups, no live prices, no MAE/MFE. Setups are tagged by me. |
| Token expires daily | One-click login every trading day, plus reminders (FR-REM). |
| Trades and orders endpoints return the current day only (VERIFY V1) | Sync every day and store raw data. CSV import fills history. |
| Static IP rule applies to order placement (VERIFY V3) | The app never places orders. |
| Automated login is discouraged | Only the official login redirect is used. No stored passwords or TOTP secrets. |

### 3.5 Assumptions to verify before relying on them

| ID | Verify | Why it matters | Status |
| --- | --- | --- | --- |
| V1 | Trades and orders endpoints return only the current trading day | Decides how critical daily sync is | **Confirmed 1 Nov 2026.** A real login and sync returned the current day only. Daily sync is therefore mandatory; a missed day is recoverable only by CSV import. |
| V2 | If I log in after 3:45 PM (for example 6 PM), sync still returns that day’s trades, and until what time | Decides the late reminder window and catch-up sync | **Partly confirmed 1 Nov 2026.** The day’s trades were still returned when logging in up to 6 PM IST. Behaviour after 6 PM is untested, so the late reminder window should not be pushed past it without a further check. |
| V3 | Read-only calls work without a whitelisted static IP on the Personal plan | Hosting without a fixed IP | **Confirmed 1 Nov 2026.** The connect flow and sync ran from a machine with no whitelisted static IP. |
| V4 | The instruments dump is available on the Personal plan | Lot size, expiry, strike | **Confirmed 1 Nov 2026.** Served unauthenticated at `https://api.kite.trade/instruments`; 110,311 rows. Columns: `instrument_token, exchange_token, tradingsymbol, name, last_price, expiry, strike, tick_size, lot_size, instrument_type, segment, exchange`. `(exchange, tradingsymbol)` is unique across the whole file, so symbol resolution is exact. Loaded by `make instruments`. |
| V5 | The login redirect supports `redirect_params` so a CSRF state value returns to the callback | Login security | **Flow confirmed 1 Nov 2026**, mechanism not isolated. The callback accepts the state from `redirect_params` or from a signed cookie, so a successful login does not prove which one carried it. Not load-bearing either way. |
| V6 | How quantity and price map to P&L for MCX (lots vs units, multiplier) | Correct commodity P&L | **Still open.** The instruments dump carries `lot_size` but no multiplier, so it does not settle this. `instrument.multiplier` stays at 1 and MCX gross P&L is unproven until checked against Console. |
| V7 | Whether positions return `pnl` and `last_price` on the Personal plan | Optional open-position display | Not verified. |
| V8 | Console tradebook CSV column names, date limits and format | CSV importer | **Confirmed 1 Nov 2026** from a real export. Thirteen lowercase columns: `symbol, isin, trade_date, exchange, segment, series, trade_type, auction, quantity, price, trade_id, order_id, order_execution_time`. `trade_date` is ISO; `order_execution_time` is ISO IST with no offset; `quantity` is float-formatted (`20.000000`); `price` carries six decimals of float noise and is quantized to four on import. **There is no `product` column**, so MIS/CNC is inferred (FR-IMP). Date limits per export still unmeasured. |
| V9 | Current charge rates per segment (brokerage, STT, exchange fees, SEBI, stamp duty, GST) | Charges engine seed data | **Transcribed, not verified.** `seed/charge_rates.json` holds the rates published at https://zerodha.com/charges/ as read on 1 Nov 2026, with its gaps listed in the file. Still needs checking against a real contract note per FR-CHG acceptance. |
| V10 | WhatsApp Cloud API setup (template approval, test recipients) and Telegram bot setup | Reminder channels | Not verified. |
| V11 | Source and format of the NSE holiday calendar | Skip reminders on holidays | **Confirmed 1 Nov 2026.** `https://www.nseindia.com/api/holiday-master?type=trading`, served to a browser-like request that has first fetched the holidays page. The `CM` key is the Capital Market segment (20 rows for 2026). Dates are `DD-Mon-YYYY`. A description ending in `*` marks a special session (Muhurat trading, 8 Nov 2026) and is stored with `is_trading_override` set, so the day still counts as a trading day. Loaded by `make holidays`, with `seed/market_holidays.json` as an offline fallback. |

## 4. Architecture and technology

### 4.1 Technology stack

Pin exact versions in lock files at build time. Use the latest stable releases.

| Layer | Choice |
| --- | --- |
| Frontend | Next.js (App Router), TypeScript (strict), Tailwind CSS, shadcn/ui, TanStack Query, Recharts (or ECharts), react-hook-form with zod |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, `kiteconnect` SDK, `httpx`, `cryptography` (Fernet), `argon2-cffi` |
| Worker | Same Python image, command `python -m app.worker`, APScheduler (or a simple minute loop) |
| Database | PostgreSQL 16 |
| Storage | S3-compatible API through `boto3` with a configurable endpoint |
| Email | **Resend HTTPS API over `httpx`** (owner's decision, 1 Nov 2026). No SMTP credentials to store and no extra dependency, since `httpx` is already used for Kite. Without a verified domain Resend sends from `onboarding@resend.dev` and delivers only to the address on the Resend account. `services/notifier.py` keeps a `Channel` protocol so SMTP can be added back without touching the reminder engine. |
| Optional chat | WhatsApp Cloud API (utility template) and Telegram Bot API, both over `httpx` |
| Proxy | Caddy (automatic HTTPS) |
| Packaging and CI | Docker, Docker Compose, GitHub Actions building images to GHCR |
| Tests | pytest, pytest-asyncio, Playwright for core flows |
| Quality | ruff, mypy, ESLint, Prettier, pre-commit |

### 4.2 Repository structure

```
tj/
  AGENTS.md                 # rules for AI assistants (Appendix A)
  Makefile                  # make dev | test | lint | migrate | seed
  docker-compose.yml  docker-compose.dev.yml  Caddyfile  .env.example
  apps/
    web/                    # Next.js
      app/ (routes)  components/  lib/api.ts  lib/format.ts
    api/
      app/
        main.py  config.py  db.py  security.py
        routers/ auth.py kite.py sync.py trades.py dashboard.py
                 analytics.py playbook.py settings.py importer.py health.py
        services/ kite_client.py sync_service.py fill_grouper.py
                  matcher.py charges.py metrics.py importer.py
                  notifier.py reminders.py benchmark.py storage.py
        models/  schemas/  worker.py
      alembic/  tests/ (fixtures/ unit/ integration/)
  infra/ backup.sh  restore.sh  bootstrap.sh
  docs/ SRS.md  RUNBOOK.md
```

### 4.3 Cross-cutting conventions

| Topic | Rule |
| --- | --- |
| Money | `numeric(14,2)` for amounts, `numeric(14,4)` for prices. Python `Decimal` only, never `float`. The API sends money as **strings**. |
| Time | Store `timestamptz` in UTC. Compute `trade_date` as the IST calendar date. Display in IST with 24-hour clock. |
| Currency format | Indian digit grouping, for example ₹1,23,456.50, using `en-IN`. |
| IDs | UUID primary keys, except Kite identifiers which are stored as text with their own unique constraints. |
| API | JSON, prefix `/api/v1`, errors as `{ "error": { "code": "...", "message": "...", "details": {} } }`, list endpoints paginated with `limit` and `cursor`. |
| Idempotency | Every import and sync operation can be repeated safely. |
| Logging | Structured JSON logs. Never log tokens, secrets, API keys or full payloads. |
| Config | Environment variables read by `pydantic-settings`. Secrets never go in git. |
| Raw data | Orders and fills keep the original payload in a `raw jsonb` column so logic can be re-run after a bug fix. |

## 5. Functional requirements

Priority key: **M** = must for version 1, **S** = should, **C** = could.

### 5.1 App login (FR-AUTH)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-AUTH-01 | There is no sign-up page. The single owner account is created by a CLI command (`make create-user`) that asks for email and password. | M |
| FR-AUTH-02 | Login with email and password. Passwords are hashed with Argon2id. | M |
| FR-AUTH-03 | Session cookie is HttpOnly, Secure, SameSite=Lax, 7 days sliding expiry. | M |
| FR-AUTH-04 | After 5 failed logins in 15 minutes, further attempts are refused for 15 minutes. | M |
| FR-AUTH-05 | Every `/api/v1` route requires a session except `/auth/login`, `/health` and `/kite/callback`. | M |
| FR-AUTH-06 | Logout destroys the session on the server. Change password is available in Settings. | M |

**Acceptance:** an unauthenticated request to any protected route returns 401. A wrong password five times locks further attempts. Cookies carry the required flags.

### 5.2 Zerodha connection (FR-KITE)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-KITE-01 | The Kite API key and secret are entered in Settings and stored encrypted (Fernet, key from `APP_ENCRYPTION_KEY`). The browser only ever receives the key masked to its last 4 characters; the secret is never returned. | M |
| FR-KITE-02 | “Connect Zerodha” calls `GET /kite/login-url`, which creates a one-time CSRF state (valid 10 minutes) and returns `https://kite.zerodha.com/connect/login?v=3&api_key=<key>` with the state passed through `redirect_params` (VERIFY V5). The browser then navigates there. | M |
| FR-KITE-03 | `GET /kite/callback?request_token=...&status=...&state=...` validates the state and `status=success`, exchanges the request token for an access token using the SDK, stores it encrypted, records `token_issued_at`, and redirects to `/?connected=1`. | M |
| FR-KITE-04 | `token_valid_until` is set to the next 06:00 IST after issue. This is only an estimate. Real validity is always checked by a live call (`profile`). | M |
| FR-KITE-05 | `GET /kite/status` returns `connected`, `expired`, `not_configured` or `error`. The live check result is cached for 60 seconds. | M |
| FR-KITE-06 | Any Kite `TokenException` marks the token expired, shows the login banner and lets the reminder logic act. | M |
| FR-KITE-07 | The header always shows a status chip: green “Zerodha connected” with the estimated expiry, or red “Login needed” with a Connect button. | M |
| FR-KITE-08 | After a successful connect the app automatically runs a catch-up sync (FR-SYNC-05). | M |
| FR-KITE-09 | Settings shows the exact redirect URL to register in the Kite Developer Console: `https://<domain>/api/v1/kite/callback`. | M |
| FR-KITE-10 | Disconnect deletes the stored token (not the trade data). | S |

**Acceptance:** with valid credentials, one click on Connect, followed by the Zerodha login, returns to the app with a green chip and a sync in progress. A replayed or expired state value is rejected.

### 5.3 Trade sync (FR-SYNC)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-SYNC-01 | “Sync now” button and `POST /sync/run` start a sync of the current day. | M |
| FR-SYNC-02 | A scheduled sync runs at 15:45 IST on trading days (time configurable). | M |
| FR-SYNC-03 | Steps: check token, refresh instruments dump if not done today (VERIFY V4), fetch orders, trades, positions and holdings, store raw payloads, upsert orders and fills, run the matcher for touched instruments, compute charges, rebuild `daily_summary` for touched dates, write the log. | M |
| FR-SYNC-04 | Fills are unique on `(account_id, kite_trade_id)`. Repeating a sync adds zero rows and reports the duplicate count. | M |
| FR-SYNC-05 | **Catch-up sync:** after a successful Kite login, if today is a trading day and no successful sync exists for today, a sync starts immediately. | M |
| FR-SYNC-06 | If the token is invalid at scheduled time, the sync is logged as `skipped_no_token`, a missed-sync alert is sent (FR-REM-08), and no retry happens until I log in. | M |
| FR-SYNC-07 | Network errors are retried 3 times with waits of 2, 4 and 8 seconds. HTTP 429 waits 1 second and retries. Calls are spaced at least 1 second apart. | M |
| FR-SYNC-08 | Only one sync can run at a time (PostgreSQL advisory lock). A second request returns “already running”. | M |
| FR-SYNC-09 | Rows with quantity ≤ 0, unknown side, or missing identifiers are rejected and counted, not stored. | M |
| FR-SYNC-10 | Each run writes a `sync_log` row: trigger, status (`success`, `partial`, `failed`, `skipped_no_token`), counts, duration and error text. The Settings page lists them. | M |
| FR-SYNC-11 | Positions and holdings snapshots are stored in `sync_log.details` for reconciliation (no UI needed in version 1). | S |

**Acceptance:** running the same sync twice yields 0 new fills the second time. Killing the network mid-sync leaves no half-written trade groups (the matcher and summaries run inside one transaction).

### 5.4 Reminders and notifications (FR-REM)

**Purpose.** The sync needs a valid token, and the token needs me to log in. If I forget, the day’s data may be lost (VERIFY V1 and V2). The app therefore reminds me by email and, optionally, WhatsApp or Telegram, and keeps reminding until the token is valid or the day is over.

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-REM-01 | A **trading day** is Monday to Friday and not listed in `market_holiday`. A holiday row can be flagged `is_trading_override` for special sessions (for example a weekend session). Reminders only run on trading days. | M |
| FR-REM-02 | **Default slots (IST, all editable, each can be switched off):** 09:00 morning, 15:00 first, 15:30 second, 15:40 final, 15:50 missed-sync alert, 18:00 catch-up, 21:00 late catch-up (off by default). Slots after the sync time are only useful if V2 is confirmed. | M |
| FR-REM-03 | The worker ticks every 60 seconds. For each enabled slot whose time has passed, it checks `notification_log` for `slot_key = YYYY-MM-DD:slot_name` per channel. If none exists and the slot is within a 20-minute grace window, it processes the slot. The grace window prevents a server restart at 14:00 from sending the 09:00 reminder. | M |
| FR-REM-04 | Before sending, the slot performs a **live token check** (cache ≤ 60 s). Valid token: log `skipped_token_valid`, send nothing. Invalid: send to every enabled channel. | M |
| FR-REM-05 | **Stop conditions:** a successful sync for today, a “Skip today” click in the UI, or the day ending. After a successful sync no more reminders are sent that day. | M |
| FR-REM-06 | **Channels.** Email (SMTP) is the default channel. Telegram and WhatsApp are optional. Each channel has an enable toggle, an encrypted destination, and a “Send test message” button. A failure in one channel never blocks the others. | M |
| FR-REM-07 | **Message content.** One line stating the problem, the minutes left until the 15:45 sync (or that the sync window has passed), and one link to `https://<domain>/connect`. No P&L, no balances, no tokens, no secrets. The link requires my app login and then forwards to the Zerodha login. | M |
| FR-REM-08 | **Missed-sync alert** at sync time if the token is invalid: states that today’s trades were not imported, tells me to log in now, and (if V1 is true) warns that data may be lost if I do not. | M |
| FR-REM-09 | **Outcome message (optional):** after a sync, email me counts (“14 new fills, 6 trades”). Net P&L is included only if the setting `include_pnl_in_notifications` is on (default off). | S |
| FR-REM-10 | **Retries:** up to 3 attempts per channel, with 30 seconds, 2 minutes and 5 minutes between attempts. After the last failure the log shows `failed` with the error and the UI shows a warning banner. | M |
| FR-REM-11 | **Quiet hours:** nothing is sent between 22:00 and 07:00 IST unless a slot is explicitly set inside that window. | S |
| FR-REM-12 | **WhatsApp:** use the Meta WhatsApp Cloud API with one pre-approved *utility* template that has two variables (minutes left, link). Settings stores phone number ID, access token, template name, language and my number in E.164 format. VERIFY V10: business setup, template approval and test-recipient rules. Utility messages are billed per delivered template message and were listed at about US$0.0014 each for India in April 2026 (a few rupees a month at 3 messages a day, but prices change, so check Meta’s current list). | S |
| FR-REM-13 | **Telegram:** bot token and chat ID, using `sendMessage`. Free and the simplest push channel. | S |
| FR-REM-14 | Settings has a notification log table (time, slot, channel, status, error) and a “Skip today” button that is also on the dashboard banner. | M |
| FR-REM-15 | A reminder to complete the daily review can be sent at 16:30 if no review exists for today. | C |

**Acceptance (all testable with an injected clock):**

1. Token invalid at 15:00, enabled email: exactly one email is sent for slot `15:00`, and none is sent if the worker ticks again at 15:01.
2. I log in at 15:10: the 15:30 and 15:40 slots log `skipped_token_valid` and send nothing.
3. Token invalid at 15:45: `sync_log` shows `skipped_no_token`, and one missed-sync alert goes out.
4. Server down from 14:00 to 15:20 and restarted: the 15:00 slot (20 minutes late is outside the grace window) is not sent, but the 15:30 slot is.
5. Email provider returns an error: three attempts are made, then the log shows `failed` and the banner appears.
6. On a holiday, nothing is sent.

### 5.5 Trade matching (FR-MATCH)

The algorithm and its worked examples are in section 7.

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-MATCH-01 | Matching input is all stored fills sorted by `filled_at`, then `kite_trade_id`. | M |
| FR-MATCH-02 | The matching key is `(account_id, instrument_token, product)`. Different products never match each other. | M |
| FR-MATCH-03 | FIFO lot matching. A **trade group** starts when the position moves from flat and ends when it returns to flat. | M |
| FR-MATCH-04 | A fill that closes a position and opens the opposite side is split by quantity. The part that closes belongs to the old group, the rest starts a new group. Allocations are stored in `trade_group_fill.quantity_used`. | M |
| FR-MATCH-05 | Open groups (position not flat) have status `open`, show realised-so-far and open quantity, and are excluded from win-rate, profit-factor and expectancy statistics. | M |
| FR-MATCH-06 | `is_intraday = true` when the first entry and last exit fall on the same IST date. | M |
| FR-MATCH-07 | Every group has a stable `group_key = account:token:product:first_entry_kite_trade_id`. Re-running the matcher rebuilds groups but keeps journal data, tags and screenshots by `group_key`. If a key disappears, its journal is kept as **orphaned** and shown in a repair list. | M |
| FR-MATCH-08 | Group fields: direction, qty\_max, avg\_entry, avg\_exit, opened\_at, closed\_at, hold\_seconds, gross\_pnl, charges\_total, net\_pnl. Averages are quantity-weighted. | M |
| FR-MATCH-09 | A position that never closes (for example an option that expires worthless) stays open. The UI offers “Close at price”, which adds a manual fill (`source = manual`) so the matcher can close it. | S |
| FR-MATCH-10 | The matcher is deterministic, idempotent and runs only for the instruments whose fills changed. | M |

### 5.6 Charges and net P&L (FR-CHG)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-CHG-01 | Charges are calculated **per order** (sum of that order’s fills) because brokerage is per executed order, then allocated to fills by turnover, then to trade groups by `quantity_used`. | M |
| FR-CHG-02 | Rates live in `charge_rate_set` rows with `effective_from`. The set in force on the fill’s trade date is used, so old trades keep old rates. | M |
| FR-CHG-03 | Segment keys: `eq_intraday`, `eq_delivery`, `fut`, `opt`, `comm_fut`, `comm_opt`, `cur_fut`, `cur_opt`. Mapping from exchange and instrument type to segment is a pure function with unit tests. | M |
| FR-CHG-04 | Components: brokerage, STT/CTT, exchange transaction charge, SEBI fee, stamp duty, GST, and an optional “other exchange levy” slot. GST applies to brokerage + exchange charge + SEBI fee (+ other levy if set). | M |
| FR-CHG-05 | Brokerage rule types: `min_of_flat_or_percent` (for example the lower of ₹20 or 0.03% of turnover), `flat`, `percent`, `zero`. Each component records the side it applies to (buy, sell or both). | M |
| FR-CHG-06 | Rounding rule is configurable (default: round each component to 2 decimals, half up). The last fill of an order absorbs the rounding remainder so allocated charges sum exactly to the order total. | M |
| FR-CHG-07 | The seed file `seed/charge_rates.json` is built by the owner from Zerodha’s brokerage calculator (VERIFY V9). **The AI must not invent any rate.** | M |
| FR-CHG-08 | Changing a rate set triggers a background recompute of the affected dates with a progress indicator. | S |
| FR-CHG-09 | A reconciliation page compares my computed daily charges and net P&L with a Console P&L file I upload, listing differences. | S |

**Acceptance:** for at least 10 real orders across equity, futures and options, computed charges match the contract note within ₹1 per order. Unit tests cover each segment.

### 5.7 CSV import (FR-IMP)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-IMP-01 | Upload a Zerodha Console tradebook CSV (VERIFY V8). A preview shows the first 20 rows, detected columns, date range and row count before anything is saved. | M |
| FR-IMP-02 | Rows become fills with `source = csv`. The trade ID column fills `kite_trade_id`. | M |
| FR-IMP-03 | Import is idempotent. Existing `(account_id, kite_trade_id)` rows are skipped and counted. An API fill always wins over a CSV fill. | M |
| FR-IMP-04 | If the CSV has no trade ID, a deterministic ID `csv:<sha1 of date,symbol,side,qty,price,order id,time>` is used, and the import refuses dates that already have API fills unless I choose “replace”. | M |
| FR-IMP-05 | Instruments are resolved from the instruments dump. Unresolved symbols create a placeholder instrument with parsed type, expiry and strike. | S |
| FR-IMP-06 | An import report lists rows read, new, duplicate and rejected (with reasons) and can be downloaded. | M |
| FR-IMP-07 | After import, the matcher, charges and summaries run for the affected range. | M |
| FR-IMP-08 | Each import has an `import_batch_id`. “Undo import” removes that batch’s fills and re-runs matching. | S |
| FR-IMP-09 | Files up to 20 MB are processed as a stream. | S |

### 5.8 Trade log and detail (FR-TL)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-TL-01 | Table columns: date, in time, out time, instrument, side, product, quantity, average entry, average exit, hold time, gross, charges, net, R, setup, tags count, screenshot icon. | M |
| FR-TL-02 | Filters: date range (presets: today, this week, this month, this FY, custom), asset class, product, direction, setup, tag, outcome (win, loss, breakeven), status (closed or open), symbol search, and **“Intraday only”, on by default**. | M |
| FR-TL-03 | Sort by any column, newest first by default. Cursor pagination, 50 rows per page, totals row for the filtered set. | M |
| FR-TL-04 | Filters are stored in the URL so views can be bookmarked. | S |
| FR-TL-05 | Detail page `/trades/[id]` shows: summary header, fills table (time, side, quantity, price, order ID, charge), charges breakdown (brokerage, STT, exchange, SEBI, stamp, GST), journal form, tags, screenshots, previous and next buttons. | M |
| FR-TL-06 | **Slippage** is shown when a planned entry exists: for a buy, average entry minus planned entry; for a sell, planned entry minus average entry. Positive means worse. Shown in ₹ and %. | S |
| FR-TL-07 | An **Open positions** panel lists open groups with open quantity and average price. | M |
| FR-TL-08 | Bulk tagging: select rows and apply a setup or tag. | C |
| FR-TL-09 | Export the filtered table to CSV. | S |

### 5.9 Journal, tags and screenshots (FR-JRN)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-JRN-01 | Fields per trade: strategy, planned entry, planned stop-loss, planned target, entry reason, exit reason, emotion (calm, confident, anxious, fearful, frustrated, greedy, bored), followed plan (yes, partly, no), execution rating 1–5, lessons learned. | M |
| FR-JRN-02 | Derived: `planned_risk_amount = qty_max × abs(planned_entry − planned_sl)`, `planned_rr = abs(target − entry) / abs(entry − sl)`, `r_multiple = net_pnl / planned_risk_amount`. If planned entry is blank it defaults to the average entry. Without a stop-loss, R is null and the trade is excluded from R statistics. | M |
| FR-JRN-03 | Strategies are managed in Settings. Seeds: ORB, Pullback, Mean Reversion, VWAP Bounce, Breakout, Breakdown, EMA Crossover, RSI Reversal, News, Other. | M |
| FR-JRN-04 | Mistake tags are managed in Settings. Seeds: FOMO entry, Moved stop-loss, Revenge trade, Exited early, Held too long, Oversized, Broke daily limit, No setup, Chased price, Averaged down. Several tags per trade. | M |
| FR-JRN-05 | Autosave with an 800 ms debounce and a visible “Saved” indicator. | M |
| FR-JRN-06 | **Screenshots:** upload by drag and drop, file picker or **paste from the clipboard**. PNG, JPEG or WebP, up to 5 MB each and 10 per trade. The browser resizes to at most 1920 px on the long side and converts to WebP. Kind: before, after or other, plus a caption. | M |
| FR-JRN-07 | Images are stored in object storage under `screenshots/{trade_group_id}/{uuid}.webp` and shown via signed URLs that expire in 5 minutes. | M |
| FR-JRN-08 | A **Needs review** filter and a count badge show closed trades without a strategy or without any tag. | S |

### 5.10 Dashboard (FR-DASH)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-DASH-01 | A global date range selector (default: this month) is stored in the URL. | M |
| FR-DASH-02 | KPI cards: net P&L, gross P&L, total charges, win rate, profit factor, expectancy, average R, trade count, average win, average loss, largest win, largest loss, max drawdown. Formulas are in section 7.4. Missing values show “–”. | M |
| FR-DASH-03 | **Equity curve** of cumulative net P&L by day, with a toggle to by-trade. A benchmark toggle adds Nifty 50 or Bank Nifty. If `starting_capital` is set in Settings, both lines are shown as percentage return. If not, the benchmark uses a second axis in percent. | M |
| FR-DASH-04 | **Calendar heatmap:** month grid where each cell shows net P&L (compact ₹ format) and trade count. Green for profit and red for loss with intensity scaled to the month’s largest absolute day, plus a +/− sign so colour is never the only cue. Non-trading days are neutral and holidays are hatched. A weekly total sits at the end of each row and a month total above. Clicking a day opens the trade log for that day. | M |
| FR-DASH-05 | Extra stats: best day, worst day, percent of green days, current winning or losing streak. | S |
| FR-DASH-06 | **Recent trades** feed shows the last 10 closed trades with instrument, setup tag and net P&L. | M |
| FR-DASH-07 | **Today card:** trades so far, net P&L so far (after a sync), and progress bars against today’s plan limits (max trades, max loss). | S |
| FR-DASH-08 | Banners for “Login needed”, “Last sync failed”, “Today not synced yet” and “Reminders failing”, with the Skip today action. | M |
| FR-DASH-09 | With 10,000 trades stored, the dashboard responds in under 1.5 seconds, using `daily_summary` instead of scanning all trades. | M |

### 5.11 Analytics (FR-AN)

All analytics respect the same filters as the trade log (date range, asset class, product, intraday only).

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-AN-01 | **Strategy breakdown:** table, bar chart of net P&L, and radar chart of win rate, profit factor, expectancy, average R and trade count, each scaled min-max across strategies. | M |
| FR-AN-02 | **Time edge:** net P&L, win rate and trade count by entry hour (IST) and by day of week, and an hour-by-weekday heatmap. | M |
| FR-AN-03 | **Holding duration** buckets: under 5 minutes, 5–30 minutes, 30–120 minutes, over 120 minutes (same day), and multi-day. Bucket edges are configurable. | M |
| FR-AN-04 | **Risk:** max drawdown (₹, % and dates), longest losing streak (trades and days), largest win and loss, average risk per trade, share of trades with a stop-loss planned, compliance with `max_risk_per_trade`, and an R-multiple histogram. | M |
| FR-AN-05 | **Mistake cost:** per mistake tag, count, share of trades, total and average net P&L, sorted by total cost. | M |
| FR-AN-06 | **Psychology:** net P&L by emotion tag and by the day’s discipline rating. | S |
| FR-AN-07 | **Overtrading and tilt (rule-based):** P&L grouped by number of trades in the day (1, 2, 3–5, 6+), and trades started within N minutes after a loss (default N = 10) with their combined result. | S |
| FR-AN-08 | Any chart or statistic built from fewer than 20 trades shows a “low sample” notice. | M |
| FR-AN-09 | A weekly summary page, generated on Saturday, lists the week’s numbers, top mistakes and rule-based observations. | C |

### 5.12 Daily playbook (FR-PB)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-PB-01 | Route `/playbook/[date]`, today by default, with a list of past days showing badges for plan done and review done. | M |
| FR-PB-02 | **Pre-market:** market bias (bullish, bearish, neutral), key levels (text), events (text and quick chips such as RBI policy, results, expiry day, budget, global cue), max loss for the day (₹), max trades, max risk per trade, and a checklist (defaults: checked news, marked levels, defined max loss, ready to follow the plan). The checklist is editable in Settings. | M |
| FR-PB-03 | **Post-market:** discipline rating 1–5, emotional state (calm, anxious, frustrated, greedy), what went well, what to improve, summary notes. | M |
| FR-PB-04 | **Plan versus actual** card computed from `daily_summary`: trades taken against max trades, loss against max loss, and whether limits were broken. | S |
| FR-PB-05 | A history view shows discipline ratings on a calendar. | C |

### 5.13 Settings (FR-SET)

Settings has tabs: **Zerodha**, **Sync and reminders**, **Charges**, **Strategies and tags**, **Import**, **Trading preferences**, **Holidays**, **Data**, **Account**.

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-SET-01 | Zerodha tab: credentials (masked), redirect URL, connect or disconnect, token status. | M |
| FR-SET-02 | Sync and reminders tab: sync time, scheduled sync toggle, reminder slots, channel settings, test buttons, notification log, sync history. | M |
| FR-SET-03 | Charges tab: rate sets with effective dates, recompute button and progress. | M |
| FR-SET-04 | Trading preferences: starting capital, max risk per trade, default max daily loss, default max trades, hold-bucket edges, revenge-window minutes, intraday-only default. | M |
| FR-SET-05 | Holidays tab: view and edit `market_holiday`, with a button to import a CSV (VERIFY V11). | M |
| FR-SET-06 | Data tab: export all journal data as a ZIP of CSV files, show last backup time and status. | S |
| FR-SET-07 | Account tab: change password. | M |

### 5.14 Benchmark data (FR-BM)

| ID | Requirement | Pri |
| --- | --- | --- |
| FR-BM-01 | A job at 16:30 IST fetches the day’s close for Nifty 50 and Nifty Bank and stores it in `benchmark_price`, and can backfill from the earliest trade date. | S |
| FR-BM-02 | A `BenchmarkProvider` interface has implementations for the NSE index history download (VERIFY availability), `yfinance` as an unofficial fallback, and manual CSV upload. | S |
| FR-BM-03 | Failures never break a sync or the dashboard. The overlay is hidden and a small “benchmark unavailable” note appears. | M |
| FR-BM-04 | The overlay is labelled “Public data, may be delayed or incomplete”. | S |

## 6. Data model

PostgreSQL 16. All tables have `created_at timestamptz not null default now()` unless stated. Create them through Alembic migrations, not by hand.

**Design rules**

- Journal data (notes, tags, screenshots) is keyed by **`group_key`** (text), not by the trade group’s UUID. The matcher can then delete and rebuild trade groups without losing my notes (FR-MATCH-07). There is deliberately no foreign key from journal tables to `trade_group`.
- Raw Kite payloads are kept in `raw jsonb`.
- Realised P&L is attributed to the IST date on which a group **closes**.

```sql
create extension if not exists pgcrypto;

create table app_user (
  id uuid primary key default gen_random_uuid(),
  email text unique not null, password_hash text not null,
  created_at timestamptz not null default now());

create table app_session (
  id text primary key, user_id uuid not null references app_user(id) on delete cascade,
  expires_at timestamptz not null, created_at timestamptz not null default now());

create table login_attempt (
  id bigserial primary key, email text, success boolean not null,
  at timestamptz not null default now());

create table broker_account (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references app_user(id),
  broker text not null default 'zerodha',
  api_key_enc bytea, api_secret_enc bytea, access_token_enc bytea,
  token_issued_at timestamptz, token_valid_until timestamptz, kite_user_id text,
  created_at timestamptz not null default now());

create table oauth_state (
  state text primary key, account_id uuid not null references broker_account(id),
  expires_at timestamptz not null, used_at timestamptz);

create table instrument (
  instrument_token bigint primary key,
  exchange text not null, tradingsymbol text not null, name text,
  segment text, instrument_type text,          -- EQ, FUT, CE, PE
  asset_class text not null,                   -- equity | fno | commodity | currency
  expiry date, strike numeric(14,4), lot_size int, tick_size numeric(10,4),
  multiplier numeric(14,4) not null default 1, -- VERIFY V6 for MCX
  updated_at timestamptz not null default now());
create index on instrument (exchange, tradingsymbol);

create table kite_order (
  order_id text primary key, account_id uuid not null references broker_account(id),
  exchange_order_id text, exchange text, tradingsymbol text, instrument_token bigint,
  transaction_type text, product text, order_type text, status text,
  quantity int, filled_quantity int, price numeric(14,4), trigger_price numeric(14,4),
  average_price numeric(14,4), placed_at timestamptz, raw jsonb not null,
  created_at timestamptz not null default now());

create table import_batch (
  id uuid primary key default gen_random_uuid(), account_id uuid not null,
  filename text, rows_read int, rows_new int, rows_dup int, rows_rejected int,
  date_from date, date_to date, created_at timestamptz not null default now());

create table fill (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references broker_account(id),
  kite_trade_id text not null, order_id text,
  exchange text not null, tradingsymbol text not null, instrument_token bigint not null,
  product text not null,                       -- MIS | NRML | CNC | MTF
  side text not null check (side in ('BUY','SELL')),
  quantity int not null check (quantity > 0),
  price numeric(14,4) not null,
  filled_at timestamptz not null,
  trade_date date not null,                    -- IST date of filled_at
  source text not null check (source in ('api','csv','manual')),
  import_batch_id uuid references import_batch(id),
  raw jsonb, created_at timestamptz not null default now(),
  unique (account_id, kite_trade_id));
create index on fill (account_id, instrument_token, product, filled_at);
create index on fill (trade_date);
create index on fill (order_id);

create table trade_group (
  id uuid primary key default gen_random_uuid(),
  group_key text not null unique,              -- account:token:product:first_entry_kite_trade_id
  account_id uuid not null, instrument_token bigint not null,
  tradingsymbol text not null, exchange text not null, asset_class text not null,
  product text not null, direction text not null check (direction in ('LONG','SHORT')),
  status text not null check (status in ('open','closed')),
  qty_max int not null, open_qty int not null default 0,
  avg_entry numeric(14,4), avg_exit numeric(14,4),
  opened_at timestamptz not null, closed_at timestamptz,
  trade_date date not null,                    -- IST date of closed_at, or opened_at if open
  hold_seconds int, is_intraday boolean not null,
  gross_pnl numeric(14,2) not null default 0,
  charges_total numeric(14,2) not null default 0,
  net_pnl numeric(14,2) not null default 0,
  matcher_version int not null default 1,
  updated_at timestamptz not null default now());
create index on trade_group (account_id, trade_date);
create index on trade_group (account_id, status, closed_at);

create table trade_group_fill (
  trade_group_id uuid not null references trade_group(id) on delete cascade,
  fill_id uuid not null references fill(id) on delete cascade,
  role text not null check (role in ('entry','exit')),
  quantity_used int not null check (quantity_used > 0),
  primary key (trade_group_id, fill_id, role));

create table charge_rate_set (
  id uuid primary key default gen_random_uuid(),
  effective_from date not null, label text, config jsonb not null,  -- see section 7.3
  created_at timestamptz not null default now());

create table order_charge (
  order_id text primary key, account_id uuid not null, segment_key text not null,
  turnover numeric(16,2) not null, brokerage numeric(12,2) not null,
  stt_ctt numeric(12,2) not null, exchange_txn numeric(12,2) not null,
  sebi numeric(12,2) not null, stamp numeric(12,2) not null,
  other_levy numeric(12,2) not null default 0, gst numeric(12,2) not null,
  total numeric(12,2) not null, rate_set_id uuid references charge_rate_set(id));

create table fill_charge (
  fill_id uuid primary key references fill(id) on delete cascade,
  brokerage numeric(12,4), stt_ctt numeric(12,4), exchange_txn numeric(12,4),
  sebi numeric(12,4), stamp numeric(12,4), other_levy numeric(12,4),
  gst numeric(12,4), total numeric(12,4) not null);

create table strategy (
  id uuid primary key default gen_random_uuid(),
  name text unique not null, description text, active boolean not null default true);

create table tag (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('mistake','attribute')),
  name text not null, active boolean not null default true, unique (kind, name));

-- Journal tables are keyed by group_key on purpose (no FK to trade_group).
create table trade_journal (
  group_key text primary key, strategy_id uuid references strategy(id),
  planned_entry numeric(14,4), planned_sl numeric(14,4), planned_target numeric(14,4),
  entry_reason text, exit_reason text, emotion text,
  followed_plan text check (followed_plan in ('yes','partly','no')),
  execution_rating int check (execution_rating between 1 and 5),
  lessons text, updated_at timestamptz not null default now());

create table trade_tag (
  group_key text not null, tag_id uuid not null references tag(id),
  primary key (group_key, tag_id));

create table screenshot (
  id uuid primary key default gen_random_uuid(), group_key text not null,
  kind text not null check (kind in ('before','after','other')),
  object_key text not null, mime text not null, size_bytes int not null, caption text,
  created_at timestamptz not null default now());
create index on screenshot (group_key);

create table daily_plan (
  trade_date date primary key, bias text, key_levels text, events text,
  max_loss numeric(14,2), max_trades int, max_risk_per_trade numeric(14,2),
  checklist jsonb, updated_at timestamptz not null default now());

create table daily_review (
  trade_date date primary key, discipline_rating int check (discipline_rating between 1 and 5),
  emotion text, went_well text, to_improve text, summary text,
  updated_at timestamptz not null default now());

create table daily_summary (
  account_id uuid not null, trade_date date not null,
  trades_count int not null, wins int not null, losses int not null, breakeven int not null,
  gross_pnl numeric(14,2) not null, charges numeric(14,2) not null, net_pnl numeric(14,2) not null,
  best_trade numeric(14,2), worst_trade numeric(14,2),
  primary key (account_id, trade_date));

create table market_holiday (
  trade_date date primary key, description text,
  is_trading_override boolean not null default false);

create table benchmark_price (
  symbol text not null, trade_date date not null, close numeric(14,2) not null,
  primary key (symbol, trade_date));

create table sync_log (
  id uuid primary key default gen_random_uuid(), account_id uuid,
  trigger text not null check (trigger in ('manual','scheduled','login_catchup','csv')),
  status text not null check (status in ('running','success','partial','failed','skipped_no_token')),
  started_at timestamptz not null default now(), finished_at timestamptz,
  fills_new int default 0, fills_dup int default 0, fills_rejected int default 0,
  orders_upserted int default 0, error text, details jsonb);

create table notification_channel (
  channel text primary key check (channel in ('email','whatsapp','telegram')),
  enabled boolean not null default false,
  config_enc bytea,                            -- encrypted JSON: destination, tokens, template
  updated_at timestamptz not null default now());

create table notification_log (
  id bigserial primary key, slot_key text not null, channel text not null,
  kind text not null,                          -- reminder | missed_sync | sync_result | test
  scheduled_for timestamptz, sent_at timestamptz,
  status text not null,                        -- sent | failed | skipped_token_valid | skipped_user
  attempts int not null default 0, error text,
  unique (slot_key, channel));

create table app_setting (key text primary key, value jsonb not null);
```

**Seed data to include in migrations or `make seed`:** default strategies and mistake tags (FR-JRN-03/04), default reminder slots (FR-REM-02) in `app_setting['reminder_slots']`, default trading preferences, and the holiday list.

## 7. Algorithms and rules

### 7.1 Sync procedure (pseudo-code)

```python
async def run_sync(trigger):
    if not advisory_lock('sync'): raise AlreadyRunning
    log = start_sync_log(trigger)
    if not kite.token_is_valid():                 # live profile() call
        finish(log, 'skipped_no_token'); notifier.missed_sync_alert(); return
    if not instruments_refreshed_today(): refresh_instruments()      # VERIFY V4
    orders = kite.orders(); trades = kite.trades()
    positions = kite.positions(); holdings = kite.holdings()        # snapshot only
    async with db.transaction():
        upsert_orders(orders)
        new, dup, rejected = upsert_fills(trades)   # unique (account_id, kite_trade_id)
        touched = instruments_touched(trades)
        for key in touched:                         # (account, token, product)
            rebuild_groups(key)                     # section 7.2
        compute_order_charges(order_ids_touched)    # section 7.3
        allocate_charges_to_fills_and_groups(touched)
        rebuild_daily_summary(dates_touched)
    finish(log, 'success', new, dup, rejected)
    notifier.sync_result(log)                        # optional, FR-REM-09
```

### 7.2 Matching (FIFO) and trade groups

```python
def match(fills):                 # fills of ONE (account, token, product), sorted
    groups, cur, lots = [], None, deque()           # lots: [fill, qty_left]
    for f in fills:
        remaining = f.quantity
        while remaining > 0:
            if not lots or lots[0].fill.side == f.side:        # opening or adding
                if cur is None:
                    cur = Group(direction='LONG' if f.side == 'BUY' else 'SHORT')
                lots.append(Lot(f, remaining)); cur.add_entry(f, remaining)
                remaining = 0
            else:                                              # closing
                lot = lots[0]; m = min(lot.left, remaining)
                cur.add_exit(f, m)
                cur.gross += pnl(cur.direction, lot.fill.price, f.price, m) * multiplier
                lot.left -= m; remaining -= m
                if lot.left == 0: lots.popleft()
                if not lots:                                   # flat: group complete
                    cur.close(); groups.append(cur); cur = None
    if cur: cur.status = 'open'; cur.open_qty = sum(l.left for l in lots); groups.append(cur)
    return groups

def pnl(direction, entry, exit, qty):
    return (exit - entry) * qty if direction == 'LONG' else (entry - exit) * qty
```

**Rules**

- The loop above handles scaling in, scaling out, partial fills and position flips without special cases. When a fill closes the position and still has quantity left, the leftover opens a new group in the same loop run.
- `group_key` = `account:token:product:` + the first entry fill’s `kite_trade_id`.
- `avg_entry` and `avg_exit` are quantity-weighted over `trade_group_fill` rows with `role = entry` and `role = exit`.
- `hold_seconds` = last exit time minus first entry time. `is_intraday` = both on the same IST date.
- `trade_date` = IST date of `closed_at` (or `opened_at` while open).
- After rebuilding groups for a key, delete groups of that key whose `group_key` no longer exists, then upsert the new ones. Journal tables are untouched.

### 7.3 Charges

**Segment mapping (pure function, unit-tested)**

| Exchange | Instrument type | Product | Asset class | Segment key |
| --- | --- | --- | --- | --- |
| NSE, BSE | EQ | MIS | equity | `eq_intraday` |
| NSE, BSE | EQ | CNC, NRML, MTF | equity | `eq_delivery` |
| NFO, BFO | FUT | any | fno | `fut` |
| NFO, BFO | CE, PE | any | fno | `opt` |
| MCX | FUT | any | commodity | `comm_fut` |
| MCX | CE, PE | any | commodity | `comm_opt` |
| CDS, BCD | FUT | any | currency | `cur_fut` |
| CDS, BCD | CE, PE | any | currency | `cur_opt` |

**Rate set JSON shape** (values come from Zerodha’s calculator, VERIFY V9; `<...>` are placeholders the owner fills in, never the AI):

```json
{
  "effective_from": "2026-04-01",
  "rounding": "half_up_2dp",
  "gst_rate": "<PERCENT>",
  "segments": {
    "eq_intraday": {
      "brokerage":    { "type": "min_of_flat_or_percent", "flat": "<RUPEES>", "percent": "<PERCENT>" },
      "stt_ctt":      { "percent": "<PERCENT>", "side": "sell" },
      "exchange_txn": { "percent": "<PERCENT>", "side": "both" },
      "sebi":         { "percent": "<PERCENT>", "side": "both" },
      "stamp":        { "percent": "<PERCENT>", "side": "buy" },
      "other_levy":   { "percent": "0", "side": "both" }
    },
    "opt": { "brokerage": { "type": "flat", "flat": "<RUPEES>" }, "...": "..." }
  }
}
```

**Procedure per order**

1. Group the order’s fills. `turnover_total = Σ quantity × price`. Split turnover into buy and sell sides (an order has one side, but keep the code general).
2. Pick the rate set with the greatest `effective_from ≤` the fill’s `trade_date`.
3. Brokerage by rule type. Each other component = `percent × turnover of the applicable side`, rounded per the rounding rule.
4. `gst = gst_rate × (brokerage + exchange_txn + sebi + other_levy)`, rounded.
5. Save `order_charge`. Allocate each component to fills by `fill turnover / order turnover`; the last fill takes the remainder so the sum is exact. Save `fill_charge`.
6. Group charges = Σ over fills of `fill_charge.total × (quantity_used / fill quantity)`. Net P&L = gross P&L − charges.

### 7.4 Metric definitions

Use closed trade groups only, with outcome by **net** P&L.

| Metric | Definition |
| --- | --- |
| Win, loss, breakeven | net > 0, net < 0, net = 0 |
| Win rate | wins ÷ all closed trades |
| Average win, average loss | mean of winning nets, mean of absolute losing nets |
| Profit factor | sum of winning nets ÷ absolute sum of losing nets (null if no losers, shown as ∞) |
| Expectancy | mean net P&L per trade, which equals `win% × avg win − loss% × avg loss` |
| R-multiple | `net_pnl ÷ planned_risk_amount`; average R is the mean over trades that have one |
| Equity curve | cumulative sum of daily net P&L from the start of the range, starting at 0 |
| Max drawdown | largest drop from a running peak of the equity curve (the peak starts at 0); also as % of `starting_capital + peak` if capital is set |
| Longest losing streak | longest run of consecutive losing trades (and of losing days) |
| Green-day rate | days with net > 0 ÷ days with at least one trade |

**Worked example.** Trade nets: +200, −50, +100, −150, 0. Wins 2, losses 2, breakeven 1, win rate 40%, average win 150, average loss 100, profit factor 300 ÷ 200 = 1.5, expectancy = 100 ÷ 5 = 20 (check: 0.4 × 150 − 0.4 × 100 = 20). Equity curve 200, 150, 250, 100, 100: peak 250, trough 100, max drawdown 150.

### 7.5 Reminder evaluation (runs every 60 seconds in the worker)

```python
async def tick(now):
    if not is_trading_day(now.date()): return
    if sync_succeeded_today(now.date()) or skipped_today(now.date()): return
    for slot in enabled_slots():                      # name, time, kind
        due = datetime.combine(now.date(), slot.time, IST)
        if not (due <= now <= due + timedelta(minutes=20)): continue   # grace window
        for ch in enabled_channels():
            key = f"{now.date()}:{slot.name}"
            if exists(notification_log, key, ch): continue            # idempotent
            if kite.token_is_valid(cache_seconds=60):
                log(key, ch, 'skipped_token_valid'); continue
            await send_with_retry(ch, build_message(slot, now))        # 3 attempts
```

## 8. Backend API

Base path `/api/v1`. JSON in and out. Money values are strings. Timestamps are ISO 8601 with offset. All routes need a session except those marked public. Errors use the envelope in section 4.3.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/login` (public), `/auth/logout`, `/auth/change-password` | App login and session |
| GET | `/auth/me` | Current user |
| GET | `/health` (public) | DB, storage and worker heartbeat |
| GET | `/kite/login-url` | Returns the Kite login URL with one-time state |
| GET | `/kite/callback` (public) | Receives `request_token`, stores token, redirects |
| GET | `/kite/status` | `connected`, `expired`, `not_configured`, `error`, with estimated expiry |
| POST | `/kite/disconnect` | Deletes the stored token |
| POST | `/sync/run` | Start a sync, returns the `sync_log` id |
| GET | `/sync/logs?limit=` | Sync history |
| GET | `/sync/status` | Running flag, last result, today synced yes or no |
| POST | `/import/tradebook/preview`, `/import/tradebook` | Multipart CSV, preview then commit |
| POST | `/import/{batch_id}/undo` | Remove a batch |
| GET | `/trades` | List with filters: `from, to, asset_class, product, direction, strategy_id, tag_id, outcome, status, intraday, q, sort, cursor, limit` |
| GET | `/trades/{id}` | Detail: group, fills, charges, journal, tags, screenshots |
| PUT | `/trades/{id}/journal` | Save journal fields (autosave) |
| PUT | `/trades/{id}/tags` | Replace tag set |
| POST | `/trades/{id}/screenshots` | Upload (multipart), returns metadata |
| DELETE | `/screenshots/{id}` | Delete |
| GET | `/screenshots/{id}/url` | Short-lived signed URL |
| POST | `/trades/{id}/manual-close` | Add a manual closing fill (FR-MATCH-09) |
| GET | `/dashboard/summary?from&to` | KPI values |
| GET | \`/dashboard/equity-curve?from&to&by=day | trade&benchmark=\` |
| GET | `/dashboard/calendar?month=YYYY-MM` | Day cells, weekly and monthly totals |
| GET | `/dashboard/recent` | Last 10 closed trades |
| GET | `/analytics/strategy`, `/time`, `/duration`, `/risk`, `/mistakes`, `/psychology`, `/overtrading` | Analytics (same filter params as trades) |
| GET, PUT | `/daily/{date}/plan`, `/daily/{date}/review` | Playbook |
| GET | `/daily?from&to` | Playbook status list |
| GET, POST, PUT, DELETE | `/strategies`, `/tags` | Managed lists |
| GET, PUT | `/settings/kite` | Credentials (secret write-only) |
| GET, PUT | `/settings/preferences` | Trading preferences |
| GET, PUT | `/settings/reminders` | Slots, quiet hours, outcome message options |
| GET, PUT | `/settings/channels/{channel}` | Channel config (destination masked) |
| POST | `/settings/channels/{channel}/test` | Send a test message |
| GET | `/notifications/log?limit=` | Notification history |
| POST | `/reminders/skip-today` | Suppress reminders for today |
| GET, POST | `/charges/rate-sets`, `/charges/recompute` | Rate sets and recompute job |
| GET, PUT | `/holidays` | Holiday list |
| POST | `/benchmark/refresh` | Fetch or backfill benchmark closes |
| GET | `/export/all` | ZIP of CSV exports |

**Example: list item from `GET /trades`**

```json
{
  "id": "9f1c...", "group_key": "acc1:256265:MIS:12345678",
  "symbol": "NIFTY25NOV24500CE", "exchange": "NFO", "asset_class": "fno",
  "product": "MIS", "direction": "LONG", "status": "closed", "is_intraday": true,
  "qty_max": 75, "avg_entry": "112.4000", "avg_exit": "121.1500",
  "opened_at": "2026-11-02T09:31:12+05:30", "closed_at": "2026-11-02T09:58:40+05:30",
  "hold_seconds": 1648, "gross_pnl": "656.25", "charges_total": "58.31", "net_pnl": "597.94",
  "r_multiple": "1.4", "strategy": "ORB", "tags": ["Exited early"], "has_screenshots": true
}
```

**Example: `GET /dashboard/summary`**

```json
{ "from": "2026-11-01", "to": "2026-11-30", "trades": 42, "net_pnl": "12480.50",
  "gross_pnl": "14120.00", "charges": "1639.50", "win_rate": "0.524",
  "profit_factor": "1.38", "expectancy": "297.15", "avg_r": "0.42",
  "max_drawdown": "3820.00", "low_sample": false }
```

## 9. User interface specification

### 9.1 Layout and style

- **Navigation:** left sidebar on desktop (Dashboard, Trades, Analytics, Playbook, Settings), bottom tab bar on phones.
- **Top bar:** Zerodha status chip (FR-KITE-07), “Sync now” button, last sync time, and the date range picker on pages that use it.
- **Banner stack** under the top bar for: login needed, sync failed, today not synced, reminders failing. The login banner has **Connect** and **Skip today** buttons.
- **Theme:** dark by default with a light toggle, one sans-serif font, tabular numerals for money.
- **Money and colour:** ₹ with Indian grouping, always with a sign (+₹1,250.00 or −₹800.00). Green and red are never the only cue.
- **Dates and times:** `02 Nov 2026`, 24-hour times, IST.
- **Accessibility:** WCAG AA contrast, full keyboard navigation, charts have a text or table alternative.
- **Every list and chart has three extra states:** loading skeleton, empty state with a clear next step (for example “No trades yet. Sync now or import a CSV”), and error with a Retry button.

### 9.2 Pages

| Route | Contents | Main requirements |
| --- | --- | --- |
| `/login` | Email and password form | FR-AUTH |
| `/connect` | Redirects to the Zerodha login (this is the link in reminders) | FR-KITE, FR-REM-07 |
| `/` Dashboard | Banners, KPI cards, equity curve, calendar heatmap, today card, recent trades | FR-DASH |
| `/trades` | Filter bar, table, open positions panel, totals | FR-TL |
| `/trades/[id]` | Summary, fills, charges, journal form, tags, screenshots, prev and next | FR-TL-05, FR-JRN |
| `/analytics` | Tabs: Strategy, Time, Duration, Risk, Mistakes, Psychology, Overtrading | FR-AN |
| `/playbook` and `/playbook/[date]` | Day list, pre-market form, post-market form, plan versus actual | FR-PB |
| `/settings/[tab]` | Tabs listed in section 5.13 | FR-SET, FR-REM |

### 9.3 Key components

`StatusChip`, `BannerStack`, `DateRangePicker`, `KpiCard`, `EquityCurveChart`, `CalendarHeatmap`, `TradeTable`, `FilterBar`, `OpenPositionsPanel`, `FillsTable`, `ChargesBreakdown`, `JournalForm` (autosave), `TagPicker`, `ScreenshotUploader` (drag, pick, clipboard paste), `StrategyRadar`, `HourWeekdayHeatmap`, `DrawdownChart`, `ReminderSlotEditor`, `ChannelCard` (email, Telegram, WhatsApp with test button), `NotificationLogTable`, `ImportWizard` (upload, preview, confirm, report).

### 9.4 Frontend rules

- The API client and types are **generated from the FastAPI OpenAPI schema** (`openapi-typescript`), so the frontend and backend never drift.
- Server data goes through TanStack Query. Filters live in the URL query string.
- Money arrives as strings and is formatted in one helper (`lib/format.ts`). No arithmetic on money in the browser except display formatting and chart scaling.
- The browser only talks to `/api` on its own origin (a proxy), never directly to Zerodha or to third-party services.

## 10. Non-functional requirements

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Performance | Dashboard under 1.5 s and trade list page under 500 ms at 10,000 trades. A sync of 500 fills finishes in under 30 s. |
| NFR-02 | Correctness | Matcher, charges and metrics modules have unit tests with 100% branch coverage. Gross P&L equals Console exactly. |
| NFR-03 | Reliability | Sync, import and matcher are idempotent and transactional. A crash never leaves half-built groups. |
| NFR-04 | Security | Argon2id, secure cookies, encrypted credentials and tokens, CSRF protection for state-changing requests, rate-limited login, no secrets in logs or URLs, dependency scanning in CI. |
| NFR-05 | Privacy | No third-party analytics or tracking. Reminder messages contain no financial figures by default. Optional AI features, if added later, are off by default and receive only aggregated statistics. |
| NFR-06 | Availability and recovery | Single server is acceptable. Backup every 24 hours (RPO 24 h) and a restore tested monthly (RTO 2 h). |
| NFR-07 | Observability | `/health`, structured logs, sync log and notification log in the UI. The worker pings an **external heartbeat URL** every 5 minutes (for example a free healthchecks.io check) so I am emailed if the worker dies, because reminders depend on it. |
| NFR-08 | Portability | No cloud-specific services. Everything configurable by environment variables. Moving servers needs only the steps in section 11.6. |
| NFR-09 | Maintainability | ruff, mypy (strict for `services/`), ESLint and Prettier pass in CI. Alembic migrations only. |
| NFR-10 | Time handling | All trading-day logic uses Asia/Kolkata. A test sets the clock to 23:59 and 00:01 IST to check date boundaries. |
| NFR-11 | Compatibility | Latest two versions of Chrome, Edge, Safari and Firefox. Usable on a 390 px wide phone. |
| NFR-12 | Compliance | Official Kite API and login redirect only. No automated login, no scraping of Zerodha pages, read-only use. |

## 11. Deployment

### 11.1 Services (Docker Compose)

```yaml
services:
  db:      { image: postgres:16, volumes: [pgdata:/var/lib/postgresql/data], env_file: .env,
             healthcheck: { test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"] } }
  api:     { image: ghcr.io/<me>/tj-api:${TAG}, env_file: .env, depends_on: [db],
             command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000" }
  worker:  { image: ghcr.io/<me>/tj-api:${TAG}, env_file: .env, depends_on: [db],
             command: python -m app.worker }          # exactly ONE worker replica
  web:     { image: ghcr.io/<me>/tj-web:${TAG}, env_file: .env, depends_on: [api] }
  caddy:   { image: caddy:2, ports: ["80:80", "443:443"], depends_on: [web, api],
             volumes: [./Caddyfile:/etc/caddy/Caddyfile, caddy_data:/data] }
  backup:  { image: ghcr.io/<me>/tj-backup:${TAG}, env_file: .env, depends_on: [db] }   # cron 02:30 IST
volumes: { pgdata: {}, caddy_data: {} }
```

```
{$DOMAIN} {
  encode zstd gzip
  handle /api/* { reverse_proxy api:8000 }
  handle        { reverse_proxy web:3000 }
}
```

### 11.2 AWS Free Plan runbook

My AWS account was created after 15 July 2025, so it is on the **Free Plan**: credits, and a limit of 6 months. When the plan ends the account closes unless I upgrade to the Paid plan, and data is kept for about 90 days. Credits remain valid for 12 months from sign-up.

1. Create a budget alert in AWS Budgets.
2. Launch **one t3.small** in Mumbai (ap-south-1), Ubuntu 24.04, 20–30 GB gp3. Check that the instance type is marked free-tier eligible.
3. Security group: SSH (22) from my IP only, 80 and 443 open (or none if I use Tailscale or a tunnel).
4. Add a 2 GB swap file. Install Docker. Never build images on the server.
5. Point a DNS name to the server. Check whether an Elastic IP or public IPv4 address uses credits.
6. Copy `.env`, `docker-compose.yml`, `Caddyfile` and the `seed/` directory, then `docker compose pull && docker compose up -d`. **`seed/` is required:** the API image is built from `apps/api`, so the repo-root seed files are outside its build context and are bind-mounted instead. Without them `app.cli seed` fails with `Not found: /srv/seed/charge_rates.json`. Note that `docker compose restart` does not pick up a new volume — use `up -d`.
7. Register `https://<domain>/api/v1/kite/callback` as the redirect URL in the Kite Developer Console.
8. Put **screenshots and backups in a bucket on another provider** (Cloudflare R2 or Backblaze B2), so closing the AWS account cannot delete them.
9. Calendar reminders at month 4 and month 5: decide to upgrade to Paid or migrate (section 11.6).

The callback is only a redirect through my own browser, so the server can sit behind Tailscale or a Cloudflare Tunnel and still work, as long as my browser can reach it.

### 11.3 CI/CD

GitHub Actions: on pull request run lint, type checks, unit and integration tests. On merge to `main` build `tj-api`, `tj-web` and `tj-backup` images and push to GHCR. Deploy is manual: SSH to the server, set `TAG`, `docker compose pull && docker compose up -d`. Migrations run when the API container starts.

### 11.4 Backups

- 02:30 IST: `pg_dump -Fc` → encrypt with `age` (public key on the server, private key kept offline) → `rclone copy` to the remote bucket.
- Keep 30 daily and 12 monthly dumps. The Data tab shows last success time. A failed backup raises a banner.
- `infra/restore.sh <dump>` restores into a clean database. Run it monthly on a scratch machine and record the result.

### 11.5 Environment variables

Listed in Appendix B. Secrets live only in the server `.env` and in GitHub Actions secrets.

### 11.6 Switching cloud provider

1. Create the new VM and install Docker.
2. Copy `.env`, compose file and Caddyfile.
3. Restore the latest backup with `restore.sh`.
4. Start the stack and check `/health`.
5. Point DNS to the new IP and update the redirect URL in the Kite Developer Console.
6. Verify one manual sync and one test reminder, then delete the old server.

## 12. Testing and acceptance

### 12.1 Test layers

| Layer | What | Tools |
| --- | --- | --- |
| Unit | Matcher, charges, metrics, segment mapping, reminder tick with an injected clock | pytest |
| Integration | Sync against saved Kite fixtures, importer, API routes with a test database | pytest, httpx, testcontainers or a Compose test DB |
| End to end | Login, mocked Kite connect, sync, tagging a trade, pasting a screenshot, calendar click-through | Playwright |

### 12.2 Golden matcher scenarios (the contract)

All scenarios use one instrument and one product unless stated. “Gross” is before charges. **These expected values must not be edited without the owner’s approval.**

| # | Fills in time order | Expected |
| --- | --- | --- |
| S1 | BUY 100 @100, SELL 100 @102 | 1 closed LONG group, gross +200 |
| S2 | BUY 50 @100, BUY 50 @100.5, SELL 100 @101.5 | 1 group, avg entry 100.25, gross +125 |
| S3 | BUY 100 @100, SELL 40 @101, SELL 60 @102 | 1 group, avg exit 101.6, gross +160 |
| S4 | SELL 50 @200, BUY 50 @198 | 1 closed SHORT group, gross +100 |
| S5 | BUY 100 @100, SELL 150 @101, BUY 50 @100.5 | Group 1 LONG gross +100 (uses 100 of the 150 sell). Group 2 SHORT entry 50 @101, exit 50 @100.5, gross +25. Total +125 |
| S6 | BUY 10 @50, SELL 10 @51, BUY 10 @52, SELL 10 @51.5 | 2 closed groups, +10 and −5 |
| S7 | BUY 100 @100 only | 1 open group, open qty 100, excluded from statistics |
| S8 | Day 1 NRML BUY 100 @100, day 2 SELL 100 @103 | 1 closed group, is\_intraday false, gross +300 |
| S9 | MIS BUY 10 @100 and NRML SELL 10 @101 (same instrument) | Two separate open groups, never matched together |
| S10 | Same Kite payload synced twice | Second run: 0 new fills, groups unchanged |
| S11 | Same `kite_trade_id` from API and CSV | One fill, the API row kept, duplicate counted |
| S12 | BUY 10 @100, BUY 10 @110, SELL 10 @120 | 1 open group, realised so far +200 (FIFO against the 100 lot), open qty 10 |
| S13 | S5 matched, journal notes saved on group 1, then matcher re-run | Notes still attached to group 1 (same `group_key`) |

**Charges tests:** one test per segment key using a real contract note from the owner, tolerance ₹1 per order, plus tests for rounding, allocation sum equals order total, and effective-date selection.

**Reminder tests:** the six acceptance cases in section 5.4, using an injected clock and a fake notifier.

### 12.3 Reconciliation (first two weeks of use)

Each evening compare, for the day: number of trades, gross P&L and total charges against Zerodha Console. Gross must match exactly. Charges within ₹1 per order. Record differences in `docs/RECONCILIATION.md` and fix before building new features.

### 12.4 Definition of done (every milestone)

- Acceptance criteria pass and tests are green in CI.
- No new lint or type errors.
- Migrations apply on an empty database and on a copy of real data.
- No secrets or personal data in logs, fixtures or git history.
- `docs/RUNBOOK.md` updated if operations changed.
- VERIFY items touched by the milestone are marked as confirmed in section 3.5.

## 13. Build plan and milestones

Estimates assume part-time work with an AI assistant. Order matters: **data capture and reminders come first**, because every day without sync is data at risk.

| Milestone | Scope | Requirements | Accept when | Est. |
| --- | --- | --- | --- | --- |
| M0 Foundation | Repo, Compose, CI, Caddy, auth, `/health`, Alembic baseline, AGENTS.md | FR-AUTH, section 4, NFR-09 | HTTPS login works locally and CI is green | 2–3 days |
| M1 Kite connect and sync | Complete V1–V5 checks, save fixtures, connect flow, sync, sync log | FR-KITE, FR-SYNC | Real sync stores today’s fills, second sync adds 0 | 4–5 days |
| M2 Reminders and first deploy | Worker, holiday table, email and Telegram, test buttons, heartbeat, deploy to AWS | FR-REM, NFR-07, section 11 | All six reminder cases pass, one real reminder received on phone, app live on my domain | 3–4 days |
| M3 Matcher | FR-MATCH with golden tests S1–S13 | FR-MATCH, 7.2 | All golden scenarios pass, journal survives re-match | 4 days |
| M4 Charges | Rate sets, per-order calculation, allocation, reconcile page | FR-CHG, 7.3 | 10 real orders within ₹1 | 3–4 days |
| M5 History import | Tradebook CSV importer for the chosen timeline (option B) | FR-IMP | Import is idempotent, daily totals match Console | 3 days |
| M6 Trade log and journal | Table, filters, detail page, journal, tags, screenshots | FR-TL, FR-JRN | I can tag a trade, paste a screenshot and find it again by filter | 5 days |
| M7 Dashboard and benchmark | KPIs, equity curve, calendar heatmap, today card, benchmark | FR-DASH, FR-BM | Dashboard under 1.5 s with 10k generated trades | 4–5 days |
| M8 Analytics | Strategy, time, duration, risk, mistakes, psychology, overtrading | FR-AN | Numbers match hand-checked examples in 7.4 | 4 days |
| M9 Playbook and settings | Daily plan and review, all settings tabs, WhatsApp channel, export | FR-PB, FR-SET, FR-REM-12 | Full daily routine works end to end | 4 days |
| M10 Hardening | Manual close for expiries, backup restore drill, accessibility pass, docs | FR-MATCH-09, NFR-06, NFR-11 | Restore drill succeeds, Lighthouse accessibility ≥ 90 | 3–4 days |

Total: roughly 6 to 8 weeks of part-time work.

## 14. Risks and open items

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Trades endpoint returns today only (V1) | Missed day cannot be recovered from the API | Reminders, catch-up sync, CSV import, visible “not synced” banner |
| Reminder worker dies silently | No reminders | External heartbeat (NFR-07), health banner |
| WhatsApp template rejected or setup is heavy (V10) | No WhatsApp reminders | Email and Telegram work without it; WhatsApp stays optional |
| Charge rates change | Wrong net P&L | Effective-dated rate sets, reconcile page |
| MCX or special instruments have different multipliers (V6) | Wrong commodity P&L | Verify against Console before trusting MCX numbers |
| Options expiring worthless leave open groups | Open positions pile up | Manual close action (FR-MATCH-09) |
| AWS Free Plan ends | Server disappears | Backups and screenshots on another provider, month 4 and 5 reminders |
| Zerodha changes plans or API terms | Sync breaks | Kite code isolated in `kite_client.py` and covered by fixtures |
| AI assistant invents details | Wrong code | VERIFY list, fixtures first, golden tests, “ask when unsure” rule |

**Decisions still needed from the owner**

1. Final choice of history import option (recommended: B, from 1 April 2026).
2. Which reminder channels to switch on first (email is mandatory; Telegram recommended as the free second channel; WhatsApp optional).
3. Domain name and DNS provider.
4. Which provider holds the bucket for screenshots and backups (R2 or B2 suggested).

## Appendix A. AGENTS.md (rules file for AI assistants)

```markdown
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
```

## Appendix B. `.env.example`

```
DOMAIN=journal.example.com
TZ=Asia/Kolkata
APP_ENV=production
APP_SECRET_KEY=change-me                 # session signing
APP_ENCRYPTION_KEY=change-me             # Fernet key for stored secrets
POSTGRES_USER=tj
POSTGRES_PASSWORD=change-me
POSTGRES_DB=tj
DATABASE_URL=postgresql+psycopg://tj:change-me@db:5432/tj
PUBLIC_BASE_URL=https://journal.example.com
S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=tj-data
S3_ACCESS_KEY=change-me
S3_SECRET_KEY=change-me
RESEND_API_KEY=change-me
RESEND_FROM=onboarding@resend.dev
REMINDER_EMAIL_TO=me@example.com
HEARTBEAT_URL=https://hc-ping.com/<uuid>
BACKUP_AGE_PUBLIC_KEY=age1...
BACKUP_RCLONE_REMOTE=r2:tj-backups
# Telegram and WhatsApp credentials are entered in Settings and stored encrypted in the database.
```

## Appendix C. Message templates

| Kind | Text |
| --- | --- |
| Email subject (before sync) | Action needed: log in to Zerodha before 3:45 PM |
| Email body (before sync) | Your Zerodha session is not connected today, so your trades cannot be imported. About {minutes} minutes are left before the 3:45 PM sync. Connect now: {link} |
| After sync time | The 3:45 PM sync window has passed and today’s trades are not imported yet. Log in now to import them: {link} |
| Missed-sync alert | Missed sync: today’s trades were NOT imported. Log in now: {link} |
| Telegram | Same text as the email body, one message, no formatting |
| WhatsApp utility template (draft for approval) | Journal reminder: please log in to Zerodha so today’s trades can be imported. {{1}} are left before the 3:45 PM sync. Connect here: {{2}} Thank you. |

Templates never contain P&L, balances, tokens or secrets. The WhatsApp template ends with plain text because Meta may reject templates that end in a variable (VERIFY V10).

## Appendix D. Kite field mapping

| Kite trade field | `fill` column |
| --- | --- |
| `trade_id` | `kite_trade_id` |
| `order_id` | `order_id` |
| `exchange`, `tradingsymbol`, `instrument_token`, `product` | same names |
| `transaction_type` | `side` |
| `quantity` | `quantity` |
| `average_price` | `price` |
| `fill_timestamp` (fallback `exchange_timestamp`) | `filled_at`, read as Asia/Kolkata, stored UTC |
| entire object | `raw` |

Orders map by the same names into `kite_order` (`order_id`, `exchange_order_id`, `status`, `order_type`, `quantity`, `filled_quantity`, `price`, `trigger_price`, `average_price`, `order_timestamp` → `placed_at`). Confirm every field name against saved real responses (VERIFY) before coding the mapper.
