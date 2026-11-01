# User manual

How to run your trading journal day to day.

This is written for the person using the app, not the person building it. For
setting up a development machine see the [README](../README.md).

---

## Contents

1. [What this app does](#1-what-this-app-does)
2. [First-time setup](#2-first-time-setup)
3. [The daily routine](#3-the-daily-routine)
4. [Reminders](#4-reminders)
5. [The screens](#5-the-screens)
6. [Importing past trades](#6-importing-past-trades)
7. [Understanding the numbers](#7-understanding-the-numbers)
8. [When something goes wrong](#8-when-something-goes-wrong)
9. [What is not built yet](#9-what-is-not-built-yet)

---

## 1. What this app does

Every evening it should be able to answer two questions: how did today go, and
why.

It does that by pulling your fills from Zerodha, grouping them into trades,
subtracting the real charges, and giving you one minute per trade to say what
you were thinking.

**What it does not do.** It never places an order, never modifies one, and
never logs in to Zerodha for you. It has no live prices and no charts of the
market. It is a record, not a terminal.

**One thing you must understand before relying on it.** Zerodha's API returns
**only the current day's trades**, and your access token expires at 6 AM the
next morning. If you do not log in to Zerodha on a trading day, that day's
trades cannot be fetched later from the API — you would have to import them
from a Console CSV instead. That single fact is why the reminders exist.

---

## 2. First-time setup

You do this once.

### 2.1 Fill in the configuration

Copy `.env.example` to `.env` and set these:

| Setting | What to put |
|---|---|
| `APP_ENCRYPTION_KEY` | A Fernet key. Generate with the command in the README |
| `APP_SECRET_KEY` | Any long random string |
| `POSTGRES_PASSWORD` | Any password. Must match the one inside `DATABASE_URL` |
| `PUBLIC_BASE_URL` | `http://localhost:3000` locally, or `https://yourdomain` once deployed |
| `KITE_API_KEY` / `KITE_API_SECRET` | From your Kite Connect app |
| `RESEND_API_KEY` | From your Resend account, for reminder emails |
| `REMINDER_EMAIL_TO` | **The email address on your Resend account** |
| `HEARTBEAT_URL` | A healthchecks.io ping URL. Optional but recommended |

> **`REMINDER_EMAIL_TO` must be your own inbox.** Until you verify a domain
> with Resend, mail is sent from `onboarding@resend.dev` and Resend will only
> deliver it to the address your Resend account is registered under. Anything
> else is accepted by the API and never arrives.

> **After editing `.env`, run `docker compose up -d`.** `docker compose
> restart` does *not* re-read the file, and you will spend an hour wondering
> why your change did nothing.

### 2.2 Start it and load the reference data

```bash
make dev
make migrate
make seed
make instruments
make holidays
make create-user
```

What each of the last four does:

- **`make seed`** — brokerage and tax rates, the ten default strategies, the
  ten default mistake tags, and the reminder schedule.
- **`make instruments`** — around 110,000 tradeable instruments from Zerodha.
  This is what turns `SBIN` into a specific NSE share. Refresh it every few
  weeks, and whenever you trade something it does not recognise.
- **`make holidays`** — the NSE trading calendar, straight from the exchange.
  Without it, reminders fire on Diwali. **Re-run it every January**, when NSE
  publishes the next year.
- **`make create-user`** — your email and password for the app itself. This is
  separate from your Zerodha login.

### 2.3 Connect Zerodha

1. In the Kite Developer Console, set your app's redirect URL to exactly:
   `<PUBLIC_BASE_URL>/api/v1/kite/callback`
2. Store your credentials, encrypted:
   ```bash
   make kite-credentials
   ```
3. Start the app, log in, and press **Connect Zerodha** in the header.

### 2.4 Check that reminders work

```bash
docker compose -f docker-compose.dev.yml exec api python -m app.cli notify-test
```

An email should arrive. If it does not, re-read the warning in 2.1 — it is
almost always `REMINDER_EMAIL_TO`.

---

## 3. The daily routine

Three moments. The whole design is built around them.

### Before the open — one minute

Open **Playbook** and write the plan: your bias, the levels you care about,
any events, and your limits for the day — max loss, max trades.

The limits are not decoration. After the close, the app shows what you
actually did against what you said you would do, and says plainly when you
went past it.

### Around 3:30 PM — one click

**Log in to Zerodha.** Press **Connect Zerodha** in the header and complete
the Zerodha login.

That is the only thing you must not forget. The token lasts until 6 AM
tomorrow; the scheduled sync runs at 3:45 PM and needs it. If you are
connected, the day imports by itself.

The header tells you where you stand:

| Chip | Meaning |
|---|---|
| **Connected** (green dot) | A valid token. The 3:45 PM sync will run |
| **Login needed** (red dot, yellow background) | No valid token. Today will not import |
| **Syncing** | A sync is running now |

### In the evening — a minute per trade

Open **Home** to see how the day went, then **Trades** to tag each one.

Tap a trade to open the detail panel: what you planned, what you actually got,
the full charge breakdown, every fill. Write down why you took it and what you
would do differently. The **Needs review** filter shows the trades you have
not tagged yet.

Then go back to **Playbook** and write the evening half: discipline rating,
how it felt, what went well, what to improve.

---

## 4. Reminders

If you are not connected to Zerodha, the app emails you. It keeps emailing
until you are connected or the day is over.

### The schedule

All times IST, on trading days only.

| Time | What it is |
|---|---|
| 09:00 | Morning nudge |
| 15:00 | First reminder |
| 15:30 | Second reminder |
| 15:40 | Last call before the sync |
| 15:50 | **Missed-sync alert** — today's trades were not imported |
| 18:00 | Catch-up |
| 21:00 | Late catch-up (**off** by default) |

### What stops them

- **Connecting to Zerodha.** The next slot checks your token, finds it valid,
  logs `skipped_token_valid` and sends nothing.
- **A successful sync.** No further reminders that day.
- **A holiday or a weekend.** Nothing is sent at all.

### What they contain

One line saying you are not connected, how many minutes are left before the
3:45 PM sync, and a link. Never your P&L, never a balance, never a token.

### Things worth knowing

- **Each slot sends at most one email.** A reminder that already went out is
  never repeated, however many times the worker ticks.
- **A slot more than 20 minutes late is skipped.** If the server was down from
  2 PM to 3:20 PM, you do not get the 09:00 reminder at 3:20.
- **If the worker has been down and restarts late, you may get several at
  once.** A worker starting at 15:50 finds the 15:30, 15:40 and 15:50 slots
  all still within their windows and sends all three. Three emails is better
  than a lost trading day.
- **Nothing is sent between 22:00 and 07:00.**

### Is the reminder system alive?

It cannot tell you itself — a dead worker sends no warnings. Set
`HEARTBEAT_URL` to a free healthchecks.io check and the worker pings it every
five minutes. If the pings stop, healthchecks.io emails you.

---

## 5. The screens

### Home

- **The card at the top** — net P&L for the selected month, with trade counts.
- **Month selector** — step back to see past months. The month is in the URL,
  so you can bookmark a particular one.
- **Metric strip** — win rate, profit factor, expectancy, average R, max
  drawdown, trade count. Scrolls sideways on a phone.
- **Calendar** — one cell per day, tinted green or red with the amount always
  printed, because colour alone is never the whole signal. Intensity scales to
  the biggest day of the month. Holidays are hatched. Tap a day to see its
  trades.
- **Equity curve** — cumulative net P&L, starting at zero.
- **Recent trades** — the last ten closed.

### Trades

Search by symbol, filter by outcome, and switch **Intraday only** off to see
positions you carried overnight. **Needs review** shows closed trades with no
setup or no tags.

The totals line covers the **whole filtered set**, not just the rows on
screen.

Tap a row to open the detail panel:

- Net P&L, quantity, average entry and exit, hold time, R-multiple
- **Journal** — planned entry, stop loss, target, why you took it, lessons,
  and an execution rating of 1 to 5
- **Charges** — brokerage, STT, exchange, SEBI, stamp duty, GST, and the total
- **Fills** — every execution with its time, side, quantity and price

### Playbook

Today's plan and review, with the plan-versus-actual card between them once
the day has trades.

### Analytics

Not built yet.

---

## 6. Importing past trades

Zerodha's API only gives you today. To bring in history, export a tradebook
from Zerodha Console and upload it.

1. Console → Reports → **Tradebook**, pick a date range, download the CSV.
2. Upload it to the import endpoint.
3. **Re-uploading the same file is safe.** It reports duplicates and adds
   nothing. Your P&L cannot be double-counted.

### One thing the importer has to guess

**Console's tradebook does not say whether a trade was MIS or CNC.** The app
works it out: a position that opens and flattens within one day is intraday, a
position carried past its own date is delivery.

This matters because the two are charged very differently — intraday pays
brokerage and 0.025% STT on the sell side, delivery pays no brokerage but
0.1% STT on *both* sides. The import report shows you the split it decided.

If a later export closes a position the app thought was carried, it
reclassifies the earlier rows and re-matches. So importing month by month in
order gives the same answer as importing everything at once.

---

## 7. Understanding the numbers

### How a trade is put together

Fills are matched **first in, first out**, per instrument and per product.
A trade starts when your position moves off flat and ends when it returns to
flat. MIS and CNC of the same share never match each other.

A fill that closes a position and keeps going is split: the part that closes
belongs to the old trade, the rest opens a new one in the other direction.

### Net P&L

```
net = gross − charges
```

Charges are worked out **per order**, not per fill, because brokerage is
capped per executed order — ₹20 or 0.03%, whichever is lower. Three fills of
one order share one cap. The order's charge is then split across its fills by
turnover, and across trades by how much of each fill they used.

Components: brokerage, STT/CTT, exchange transaction charge, SEBI fee, stamp
duty, and GST at 18% on brokerage + exchange + SEBI. GST never applies to STT
or stamp duty.

> **The rates have not been checked against your contract notes.** They were
> transcribed from Zerodha's published charges page. Compare a few days
> against Console before trusting net P&L to the rupee. Known gaps are listed
> at the top of `seed/charge_rates.json` — the largest is that STT on options
> exercised at expiry is not modelled.

### R-multiple

`R = net P&L ÷ planned risk`, where planned risk is
`quantity × |planned entry − stop loss|`.

**No stop loss means no R.** The trade is left out of R statistics rather than
counted as zero. If you leave planned entry blank, your actual average entry
is used instead.

### What is counted, and what is not

- Statistics use **closed trades only**. An open position has no outcome yet
  and is excluded from win rate, profit factor and expectancy.
- Outcome is decided by **net** P&L, not gross. A gross winner that charges
  turn negative is a loss.
- **Breakeven is its own outcome**, not a loss.
- **Profit factor is blank, not zero, when you have no losing trades.** You
  cannot divide by nothing.
- Under 20 closed trades, the app says **"Treat with caution"** rather than
  implying the numbers mean something.

### Dates and times

Everything is stored in UTC and shown in IST. A trade belongs to the IST day
it **closed** on, so a position opened Monday and closed Tuesday counts as
Tuesday's.

---

## 8. When something goes wrong

### "Login needed" and I just logged in

The token is checked live against Zerodha, and the answer is cached for 60
seconds. Wait a minute and refresh. If it persists, press Connect again — a
master logout from Kite web kills the token early.

### Today's trades did not import

Check **Settings → sync history** (not built yet; for now, `make worker-logs`
or the `/api/v1/sync/logs` endpoint). A `skipped_no_token` entry means you
were not connected at 3:45 PM.

If you log in later the same day, run a sync manually with the button in the
header. Zerodha has returned the full day's trades up to at least 6 PM in
testing. Later than that is untested — if it fails, export a Console tradebook
and import it.

### I am not getting reminder emails

In order of likelihood:

1. `REMINDER_EMAIL_TO` is not the address on your Resend account.
2. You edited `.env` and ran `docker compose restart` instead of `up -d`.
3. The worker is not running — check `make worker-logs`.
4. It is a holiday or a weekend. Nothing is sent, by design.
5. You were already connected. Check the notification log for
   `skipped_token_valid`.

Test it directly with `python -m app.cli notify-test`.

### The dashboard is empty

It opens on the **current month**. If your trades are in a previous month,
step the month selector back.

### Login does nothing and the page stays put

`PUBLIC_BASE_URL` is set to an `https://` address while you are browsing over
plain HTTP. That makes the session cookie `Secure`, and the browser drops it
silently. Set it to `http://localhost:3000` for local use and run
`docker compose up -d`.

### A symbol shows up as unresolved after an import

The instruments master does not have it. Run `make instruments` and import
again. The trade is still recorded correctly; it just has a placeholder
instrument.

---

## 9. What is not built yet

Being plain about this so you are not hunting for things that do not exist:

- **Analytics pages.** The page is a placeholder.
- **Settings UI.** Rates, reminder slots, strategies, tags and preferences all
  exist in the database but have no screens. Change them with `make seed` or
  by editing the tables.
- **Screenshots.** The secure upload mechanism exists; the attach-an-image
  flow does not.
- **"Skip today"** for reminders. The backend supports it; there is no button.
- **Telegram and WhatsApp** reminders. Email only.
- **Backup and restore scripts.** Nothing automated — take your own
  `pg_dump` until these land.
- **CSV export** of the filtered trade log.

Deployment assets exist and are syntax-checked, but have **not been run on a
real server yet**.
