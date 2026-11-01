# SCREENS.md: screen layouts and behaviour (mobile first)

Wireframes are for a 390 px wide phone. Visual rules are in `DESIGN.md`; requirement IDs refer to `SRS.md`. Build the phone layout first, then adapt upward. Wireframes are structure only, not final visuals.

Legend: `[ ]` button or control, `( )` chip, `░` skeleton, `▓` filled bar.

---

## 1. Login (`/login`)

```
┌────────────────────────────┐
│                            │
│   Trading journal          │
│                            │
│   Email                    │
│   [______________________] │
│   Password                 │
│   [______________________] │
│   [        Log in        ] │
│                            │
└────────────────────────────┘
```

- Centred, single column, max width 360 px. No marketing copy.
- Errors under the field: "Email or password is incorrect." After 5 failures: "Too many attempts. Try again in 15 minutes."
- Password field has a show/hide control. Autofill and password managers must work (`autocomplete` attributes).
- Requirements: FR-AUTH.

---

## 2. Home (`/`)

```
┌────────────────────────────┐
│ Mon 02 Nov   ● Connected ↻ ⚙│  header
├────────────────────────────┤
│ Zerodha login needed. Today│  banner (only when needed)
│ imports at 3:45 PM.        │
│ [Connect Zerodha] [Skip today]│
│                            │
│ ┌────────────────────────┐ │  Today card
│ │ Today                  │ │
│ │ +₹2,480.50             │ │  display figure
│ │ 6 trades  4 wins  2 losses│
│ │ Trades 6 of 8  ▓▓▓▓▓▓░░│ │  plan limit bar
│ └────────────────────────┘ │
│                            │
│ November  +₹12,480.50      │  section
│ 42 trades                  │
│ Win rate 52% │ Profit factor 1.38 │ Expectancy ₹297 │  (scrolls sideways)
│                            │
│ November 2026       ‹   ›  │
│  M   T   W   T   F   S   S│
│ ░░  ░░  ░░  ░░  ░░  ░░  ░░ │  calendar grid
│ ...                        │
│ Week 1             +₹3,100 │
│                            │
│ Equity curve   1M 3M FY All│
│ [        chart 200 px     ]│
│                            │
│ Recent trades              │
│ NIFTY 24500 CE  (Long) +₹598│
│ 09:31 to 09:58  75 qty  ORB│
│ ────────────────────────── │
│ ...                        │
├────────────────────────────┤
│ Home  Trades Analytics Playbook│  bottom nav
└────────────────────────────┘
```

**Order on phone (top to bottom):** banner, Today card, month summary and metric strip, calendar, equity curve, recent trades.

**Behaviour**
- Date range for the month section follows the visible calendar month. The equity curve has its own range chips (1M, 3M, FY, All).
- Tap a calendar day: day sheet (screen 3).
- Tap a recent trade: trade detail.
- Pull down to refresh the data on screen. The header sync button runs a real sync (FR-SYNC-01).
- The Today card shows "Not synced yet" in `--slate` instead of a figure before the first sync of the day, with a quiet "Sync now" button if the token is valid.
- Plan limit bar appears only if a plan exists for today; turns text `--loss` ("Over your plan") when exceeded.

**States**
- First run (no trades): replace the page body with the empty state: "No trades yet. Sync now or import a CSV file." and two buttons.
- Loading: skeleton for each block at its final height.
- Token expired: banner as above; the status chip shows "Login needed".

**Desktop (1024 px and up):** sidebar plus a 12-column grid. Row 1: Today card (4 cols) and month summary with metric strip (8 cols). Row 2: calendar (5 cols) and equity curve (7 cols). Row 3: recent trades (12 cols) as a table.

Requirements: FR-DASH, FR-KITE-07.

---

## 3. Day sheet (bottom sheet from the calendar)

```
┌────────────────────────────┐
│ ───                        │
│ Mon 02 Nov 2026            │
│ +₹2,480.50                 │
│ 6 trades   Charges ₹212.40 │
│                            │
│ Plan: bullish, max 8 trades│
│ Review: 4 of 5, calm       │
│                            │
│ NIFTY 24500 CE      +₹598  │
│ BANKNIFTY ...       −₹310  │
│ ...                        │
│ [Open playbook] [View all] │
└────────────────────────────┘
```

- Shows plan and review summaries when they exist, otherwise a quiet link "Add plan" or "Add review".
- Each trade row opens trade detail. "View all" opens the Trades list filtered to that day.

---

## 4. Trades list (`/trades`)

```
┌────────────────────────────┐
│ Trades        ● Connected ↻│
├────────────────────────────┤
│ [ Search symbol    ] [Filters 2]│  sticky
│ (This month) (Intraday) (Needs review 3)│
├────────────────────────────┤
│ Showing 42 trades   Net +₹12,480│
│ NIFTY 24500 CE (Long)  +₹598│
│ 09:31 to 09:58  75 qty  ORB │
│ ──────────────────────────  │
│ RELIANCE (Short)       −₹310│
│ 10:12 to 10:20  50 qty  No setup│
│ ...                         │
└────────────────────────────┘
```

- Active filters appear as chips under the bar; tapping a chip removes it.
- "Intraday" chip is on by default (FR-TL-02).
- "Needs review" chip uses the marker colour and shows the count.
- Infinite scroll with cursor pagination (50 per page). A totals line sits above the list and reflects the current filters.
- Open positions appear in their own group at the top: "Open positions (1)". Rows show quantity and average price, no P&L.
- Rows that arrived in the latest sync flash the marker once (DESIGN.md, motion).
- Desktop: table with sortable columns; filter bar inline instead of a sheet.

### 5. Filters sheet

```
┌────────────────────────────┐
│ ───                        │
│ Filters                    │
│ Date    (Today)(Week)(Month)(FY)(Custom)│
│ Asset   (Equity)(F&O)(Commodity)(Currency)│
│ Product (MIS)(NRML)(CNC)   │
│ Direction (Long)(Short)    │
│ Outcome (Win)(Loss)(Breakeven)(Open)│
│ Setup   [ choose…        ] │
│ Mistake [ choose…        ] │
│ Intraday only   [ toggle ] │
│ [Clear]        [Show 42 trades]│
└────────────────────────────┘
```

- The primary button shows the live result count.
- Filters are written to the URL, so the view can be bookmarked (FR-TL-04).

---

## 6. Trade detail (`/trades/[id]`)

```
┌────────────────────────────┐
│ ‹ Trades          3 of 42  │
│ NIFTY 24500 CE             │
│ (Long) (MIS) (Intraday)    │
│ +₹597.94 net               │  display figure
│ Gross +₹656.25  Charges ₹58.31│
│ Entry 112.40  Exit 121.15  │
│ 09:31 to 09:58  27m  75 qty│
│ R 1.4                      │
├────────────────────────────┤
│ Setup and notes            │  journal section
│ Setup      [ ORB          ]│
│ Planned entry [   ] Stop [  ] Target [  ]│
│ Why did you enter?         │
│ [ text area               ]│
│ Why did you exit?          │
│ [ text area               ]│
│ How did it feel? (Calm)(Anxious)(Greedy)…│
│ Followed my plan? (Yes)(Partly)(No)│
│ Execution 1 2 3 4 5        │
│ Mistakes (+ Add)           │
│ (Moved stop-loss) (Exited early)│
│ What did you learn?        │
│ [ text area               ]│
│ Screenshots (3)            │
│ [thumb][thumb][thumb] [+ Add photo]│
├────────────────────────────┤
│ Fills (4)                  │
│ 09:31:12 BUY  75 @ 112.40  │
│ ...                        │
│ Charges  Brokerage 20.00   │
│ STT …  Exchange …  GST …   │
├────────────────────────────┤
│  [ ‹ Previous ]  [ Next › ]│  sticky bar above nav
└────────────────────────────┘
```

**Behaviour**
- Page order puts the journal before fills, because writing the reason is the main task on this page.
- Autosave 800 ms after the last change; a small "Saved" text appears in the header and fades. No Save button (FR-JRN-05).
- Planned entry, stop and target use the decimal keypad. When a stop is set, R updates live.
- Mistake chips open a multi-select sheet with the managed list and an "Add mistake type" action.
- Add photo opens the photo library or camera. Thumbnails open a full-screen viewer with pinch zoom and a before/after/other label.
- Previous and Next move within the current filtered list. Horizontal swipe is an optional extra, never the only way.
- Open trades: the display figure area shows "Open" with open quantity; a "Close at price" action appears in the overflow menu (FR-MATCH-09).
- Desktop: two columns. Left: summary, fills and charges. Right: journal and screenshots. Previous and Next move to the header.

Requirements: FR-TL-05, FR-JRN.

---

## 7. Analytics (`/analytics`)

```
┌────────────────────────────┐
│ Analytics         ● Connected│
│ (This month) (Intraday) (All setups)│
│ Strategy  Time  Duration  Risk  Mistakes  More│  scrollable tabs
├────────────────────────────┤
│ Net P&L by setup           │
│ ORB          ▓▓▓▓▓▓▓  +₹6,200│
│ Pullback     ▓▓▓▓    +₹3,100│
│ VWAP bounce  ▓▒     −₹1,150 │
│ Based on 12 trades. Treat with caution.│
│                            │
│ Setup        Trades Win  PF │
│ ORB             14  57%  1.9│
│ ...                         │
│ [ View as table ]           │
└────────────────────────────┘
```

- The filter chips apply to all tabs.
- Tab contents follow FR-AN-01 to FR-AN-07. Each tab is a vertical stack: one chart, one small table, one plain-language summary line.
- Time tab: bars by hour first; the hour by weekday heatmap sits below and scrolls sideways if needed.
- Risk tab: key figures as a metric list (max drawdown, longest losing streak, largest win and loss, average risk), then the R histogram.
- Mistakes tab: ranked rows "Moved stop-loss, 6 trades, −₹3,420".
- Radar chart only on the Strategy tab, below the bars.

---

## 8. Playbook (`/playbook`, `/playbook/[date]`)

```
┌────────────────────────────┐
│ Playbook                   │
│ Mon 02 Nov   Plan ✓  Review ·│  chips for status (text, not symbols only)
│ Tue 03 Nov   Plan ✓  Review ✓│
│ ...                         │
└────────────────────────────┘

[/playbook/2026-11-02]
│ Before the market          │
│ Bias (Bullish)(Bearish)(Neutral)│
│ Key levels [ text        ] │
│ Events (RBI policy)(Results)(Expiry)(Budget)(Global cue)│
│ Max loss [₹    ] Max trades [  ] Max risk per trade [₹   ]│
│ Checklist                  │
│ [ ] Checked news           │
│ [ ] Marked levels          │
│ ...                        │
│ After the market           │
│ Today: 6 trades, +₹2,480 against a limit of 8│
│ Discipline 1 2 3 4 5       │
│ Mood (Calm)(Anxious)(Frustrated)(Greedy)│
│ What went well [ text ]    │
│ What to improve [ text ]   │
```

- Two sections on one scrolling page; the first section expands by default before 15:30 IST, the second after.
- Autosave like the journal. Past days are editable.
- The "Today: …" line compares real results with the plan; text turns `--loss` if a limit was broken.
- Use text labels for status ("Plan done", "Review missing") along with any symbol.

---

## 9. Settings (`/settings`)

Phone: a list of rows, each opening its own screen (not tabs).

```
┌────────────────────────────┐
│ Settings                   │
│ Zerodha                    │  connected, token status
│ Sync and reminders         │
│ Charges                    │
│ Strategies and tags        │
│ Import history             │
│ Trading preferences        │
│ Holidays                   │
│ Data and backups           │
│ Account                    │
└────────────────────────────┘
```

**Zerodha screen.** API key (masked), secret (write-only: "Replace secret"), redirect URL with a Copy button and the line "Add this URL in the Kite Developer Console", token status, Connect or Disconnect.

**Sync and reminders screen**
```
│ Daily sync                 │
│ Time  [15:45]   [on]       │
│ Reminders (email, Telegram, WhatsApp)│
│ 09:00 Morning        [on]  │
│ 15:00 First          [on]  │
│ 15:30 Second         [on]  │
│ 15:40 Final          [on]  │
│ 15:50 Missed sync    [on]  │
│ 18:00 Catch-up       [on]  │
│ 21:00 Late catch-up  [off] │
│ Channels                   │
│ Email     me@…   [on] [Send test]│
│ Telegram  not set  [Set up]│
│ WhatsApp  not set  [Set up]│
│ Recent notifications       │
│ 02 Nov 15:00 Email  Sent   │
│ ...                        │
│ Sync history               │
│ 02 Nov 15:46 Scheduled  Success  14 new│
```

- Time pickers use the native time input on phones.
- "Send test" shows the result inline: "Sent to me@…" or the exact error.
- Failed channels show a red "Failing" label with the last error.

**Import history screen (wizard)**
1. Choose range: This financial year (recommended), Last 30 days, Two years, Custom.
2. Pick the Console tradebook CSV file.
3. Preview: first 20 rows, detected date range, row count. Button "Import".
4. Report: rows read, new, duplicate, rejected, with a "Download report" link and an "Undo import" button.

---

## 10. Connect Zerodha flow

```
Tap Connect (banner, chip or reminder link)
→ /connect (needs app login if the session expired)
→ Zerodha login page (their screen)
→ back to the app: "Connected. Syncing today's trades…"
→ Home with a progress line, then the new rows flash
```

- During the callback show one calm screen: "Finishing connection with Zerodha." If it fails: reason and a "Connect again" button.
- After success, the status chip changes to Connected and the Today card refreshes.

---

## 11. System states (apply to every screen)

| State | What to show |
|---|---|
| Offline | A banner "You are offline. Showing saved data." Disable actions that need the network. |
| Token expired | Login banner and chip, sync buttons say "Connect Zerodha" instead of "Sync now". |
| Sync running | Header spinner, the Today card shows "Syncing…", no layout shift. |
| Sync failed | Banner with the reason, "Try again" and "Details" (opens sync log). |
| Reminders failing | Banner "Reminders are not reaching you on WhatsApp" with a link to Settings. |
| Empty | One sentence and one action, no illustration. |
| Error loading | "Could not load trades." with a Retry button. Never a blank screen. |
| Not a trading day | Today card says "Market closed today" and hides plan limit bars. |

---

## 12. Responsive summary

| Width | Navigation | Lists | Filters | Detail |
|---|---|---|---|---|
| Below 768 | Bottom tabs | Two-line rows | Bottom sheet | One column, journal first |
| 768 to 1023 | Bottom tabs | Rows with extra columns | Bottom sheet becomes dialog | Two columns |
| 1024 and up | Left sidebar | Tables | Inline filter bar | Two columns, prev/next in header |
