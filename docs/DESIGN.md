# DESIGN.md: TJ design system (mobile first, light theme only)

Read this before writing any UI. If a UI task conflicts with this file, this file wins. Screen layouts are in `docs/SCREENS.md`.

## 1. Brief

**Subject.** A private trading journal for one Indian intraday trader.

**How it is used.** Mostly on a phone. Three moments matter:
1. Before the market opens: write the plan (a minute).
2. Around 3:30 PM: log in to Zerodha so the day imports.
3. In the evening: see how the day went, then tag each trade and note why (under a minute per trade).

**Job of the design.** Make it quick to see how the day went and why, and quick to record the reason on a phone, one thumb.

**Tone.** Calm, exact, unshowy. A trading journal should not cheer for wins or scold for losses.

**Theme.** Light only in version 1. Do not add `dark:` classes, a theme toggle or dark tokens. Set `color-scheme: light`.

## 2. Direction: the marked-up ledger

Cool, near-white pages with graphite type, like a printed contract note. One highlighter-yellow marker is used the way a trader marks a page: *today*, *what just changed*, *what needs attention*. That marker is the single memorable element. Everything else stays quiet.

## 3. Principles

1. **Phone first.** Design at 390 px wide. Desktop is the phone layout with more room, not a different product.
2. **Numbers are the content.** Money gets the biggest type, tabular numerals, right alignment, and no decoration.
3. **One loud thing.** The highlighter appears only on: today, rows that just synced, "needs review", and the active nav item. Never as a large background.
4. **Rows, not cards.** Lists are divided rows. A card is allowed only for the Today summary and bottom sheets. Never a card inside a card.
5. **Calm about money.** No confetti, flames, streak badges, trophies, or alarm styling for losses. A loss is red text with a minus sign. A win is green text with a plus sign.
6. **Every state is designed.** Loading, empty, error, offline, login expired, sync running.

## 4. Things that make an interface look machine-generated: do not do these

- Purple or blue gradients, gradient text, glow, glassmorphism, neumorphism.
- Cream background with a serif headline and a terracotta accent.
- Near-black background with one neon accent.
- Identical rounded cards for everything, each with the same soft grey shadow.
- Cards nested in cards.
- ALL CAPS tracked-out labels, small "eyebrow" labels above every heading.
- Meta text joined with middle dots (`A · B · C`) and arrows appended to buttons (`View all →`).
- A monospace face for small labels.
- Emoji or stock illustrations as icons or decoration.
- Fade-and-slide-up entrance animation on every section; hover animation on every card.
- Large hero number with a gradient pill beside it.
- The unthemed default shadcn grey look. Always apply the tokens below.

## 5. Colour tokens

Names are used in code. Never write raw hex values in components; use the tokens.

| Token | Hex | Use |
|---|---|---|
| `--chalk` | `#F4F6F8` | Page background |
| `--sheet` | `#FFFFFF` | Surfaces: sheets, inputs, the Today card |
| `--fog` | `#EAEEF2` | Pressed rows, skeletons, quiet fills |
| `--rule` | `#D9DFE6` | 1 px dividers and borders |
| `--graphite` | `#1A1F26` | Main text, primary button background |
| `--slate` | `#55606E` | Secondary text and inactive icons |
| `--marker` | `#FFE27A` | The highlighter (see principle 3) |
| `--marker-soft` | `#FFF3C4` | Soft highlight for banners and fading row flash |
| `--profit` | `#0F7A55` | Positive P&L text and icons |
| `--profit-1` `-2` `-3` | `#E3F3EC` `#BFE3D1` `#8CCBAE` | Calendar and bar tints, lightest to strongest |
| `--loss` | `#B8322A` | Negative P&L text and icons |
| `--loss-1` `-2` `-3` | `#FBE7E4` `#F4C4BE` `#EA9A91` | Calendar and bar tints |
| `--focus` | `#2457D6` | Keyboard focus ring and text links only |

**Rules**

- Text on any tint is `--graphite`, except the P&L number which keeps `--profit` or `--loss` on `--sheet` or `--chalk` only.
- Every text and background pair must pass WCAG AA (4.5:1 for text under 18 px). The values above are chosen to pass; confirm with an automated check (axe) in CI and fix the token, not the component, if one fails.
- Colour is never the only signal. P&L always has a sign (`+` or `−`). Calendar cells always print the amount.
- The primary button is graphite with white text. There is no brand-coloured button.

**Calendar intensity.** `intensity = abs(day_pnl) / max(abs(day_pnl) in the visible month)`. Under 0.33 use tint 1, under 0.66 tint 2, otherwise tint 3. Profit uses the profit tints, loss the loss tints. No-trade days use no fill. Holidays use a diagonal hatch in `--rule`.

## 6. Typography

**Family.** IBM Plex Sans (weights 400, 500, 600) and its sibling IBM Plex Sans Condensed (500, 600) for dense numbers on narrow screens. Load with `next/font/google`, Latin subset, `display: swap`. Check that the ₹ sign (U+20B9) renders in both. Fallback stack: `system-ui, "Segoe UI", Roboto, sans-serif`.

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `display` | 40 / 44 | 600 | The single hero figure (Today net P&L) |
| `title` | 24 / 30 | 600 | Page titles |
| `section` | 18 / 24 | 600 | Section headings |
| `body` | 16 / 24 | 400 | Body text, notes, inputs |
| `row` | 16 / 22 | 500 | Row titles, symbols |
| `secondary` | 14 / 20 | 400 | Supporting text, in `--slate` |
| `caption` | 12 / 16 | 400 | Smallest allowed text, in `--slate` |
| `figure` | 13 / 16 | 600, Condensed | Calendar cell amounts, table numbers |

**Rules**

- Sentence case everywhere. No all caps. No letter-spacing, except −0.01em on `display` and `title`.
- All numbers use `font-variant-numeric: tabular-nums`. Numbers are right-aligned in columns.
- Use the true minus sign `−` (U+2212) in displayed negative amounts.
- Inputs are at least 16 px so iOS Safari does not zoom on focus.
- Notes and long text: at most 70 characters per line.
- Do not use a separate display typeface. Hierarchy comes from size, weight and space.

## 7. Layout, spacing, shape

- **Spacing scale (4 px base):** 4, 8, 12, 16, 24, 32, 48.
- **Gutters:** 16 px on phones, 24 px from 768 px. Desktop content max width 1120 px.
- **Rhythm:** 32 px between sections. Rows have no gap and are divided by a 1 px `--rule`.
- **Row height:** at least 56 px on phones.
- **Touch targets:** at least 44 × 44 px. Primary actions 48 px high.
- **Breakpoints:** base is phone (0–639), `md` 768 (tablet: two columns where useful), `lg` 1024 (sidebar navigation), `xl` 1280 (content capped at max width).
- **Safe areas:** use `env(safe-area-inset-*)` for the bottom nav, sheets and sticky bars. Use `dvh`, never `100vh`.
- **Radius (varies by role, not one value for everything):** 6 for inputs, chips and calendar cells; 10 for buttons; 16 for the Today card; 20 on the top corners of sheets.
- **Elevation:** none by default; 1 px `--rule` borders instead. Only sheets have a shadow: `0 -8px 24px rgba(26,31,38,0.12)`.
- **Alignment:** left-aligned text. Centre only empty-state messages and the login form.

## 8. Navigation

**Bottom tab bar (phones, below 1024 px)**
- Four items: **Home, Trades, Analytics, Playbook**. Settings is a gear in the header because it is used rarely.
- Height 56 px plus the safe-area inset. Always visible. 1 px `--rule` top border.
- Active item: filled graphite icon, label in 600 weight, and a `--marker` pill (40 × 28, radius 14) behind the icon. Inactive: `--slate`.
- Trades shows a count badge (graphite circle, white number) when trades need review.

**Header (56 px, not sticky)**
- Left: page title, or today's date on Home.
- Right: connection status chip, sync icon button, settings gear.
- Status chip states: *Connected* (small green dot and text), *Login needed* (small red dot, text, and `--marker-soft` background), *Syncing* (spinner and text).

**Desktop (1024 px and up):** a 232 px left sidebar with the same four items and Settings at the bottom. No bottom bar.

**Sticky elements:** the bottom nav always; the filter bar under the header on list pages; the previous/next bar on trade detail.

## 9. Components

**Buttons**
- Primary: graphite background, white text, radius 10, 48 px high, text states the action ("Connect Zerodha", "Save plan").
- Secondary: white background, 1 px `--rule` border, graphite text.
- Quiet: no border, `--slate` text, for low-priority actions.
- Destructive: secondary style with `--loss` text. Always asks for confirmation in a sheet.
- No arrows or icons appended to labels. A leading icon is allowed when it adds meaning (sync).

**Chips and tags.** Radius 6, 28 px high, `--fog` background, graphite text. Selected: `--graphite` background, white text. "Needs review" uses `--marker`.

**Inputs.** 48 px high, white background, 1 px `--rule` border, radius 6, 16 px text. Label above in `secondary`. Error: `--loss` border and message below. Numeric fields use `inputmode="decimal"`.

**Segmented control and tabs.** Text with an underline of 2 px graphite on the active item. Scrollable horizontally when they do not fit. No pill-shaped tab styling.

**Bottom sheet.** The default for filters, day details, journal editing, and confirmations on phones. Top radius 20, drag handle 36 × 4 in `--rule`, max height 90 dvh, scrim `rgba(26,31,38,0.4)`. Becomes a centred dialog (max 480 px) from 768 px. Use the shadcn Drawer (vaul).

**Banner.** Full width under the header, `--marker-soft` background, 1 px `--rule` bottom border, plain text and at most two actions. One banner at a time visible; others collapse into "2 more notices".

**Today card.** The one card on Home: white, radius 16, 1 px `--rule` border, 16 px padding. Holds the display figure and a short line of counts.

**Trade row (phones).** Two lines in one row:
- Line 1: symbol (`row`) and direction chip on the left, net P&L (`figure`, right-aligned, signed, coloured) on the right.
- Line 2 (`secondary`): entry to exit time, quantity, and strategy name as separate spans with spacing, not joined by punctuation.
- A small image icon appears on the right of line 2 when screenshots exist. An open trade shows an "Open" chip instead of P&L.
- From 768 px the same data becomes a table with columns; numbers right-aligned, Condensed figures.

**Calendar (month).**
- 7 columns, cells about 46 px wide on a 360 px screen, 52 px tall, radius 6, 2 px gap.
- Day number top-left (caption, 11 px allowed here). Net P&L centred in `figure`, compact format (`+1.2k`, `−850`).
- Today: a 2 px `--marker` ring. Selected day: `--marker` fill behind the number.
- Tap a day to open the day sheet (SCREENS.md, screen 3). A weekly total sits at the right on tablet and as a row under each week on phones.

**Metric strip.** A horizontally scrollable row of compact metrics (win rate, profit factor, expectancy, average R). Each item: label in `caption`, value in `row`, divided by 1 px rules, no boxes.

**Toast.** Bottom, above the nav, graphite background, white text, 3 seconds, one line, never covers the nav. Uses the same verb as the action ("Saved", "Synced").

**Skeletons.** `--fog` blocks with the exact size of the final content. Very subtle opacity pulse, off under reduced motion.

**Empty state.** Centred, one sentence saying what is missing, one primary action. No illustration.

## 10. Data visualisation

- **Library:** Recharts, styled by hand. No default Recharts colours.
- **Equity curve:** one 2 px graphite line, a dashed 1 px `--rule` zero line, no area gradient. Fill between the line and zero with `--profit-1` above zero and `--loss-1` below. The last value is labelled directly at the line end. Benchmark: a dashed `--slate` line, labelled at its end instead of a legend.
- **Phone interaction:** touch and drag scrubs the line and shows the date and value pinned above the chart. Chart height 200 px on phones, 280 px on desktop.
- **Bars:** profit bars `--profit`, loss bars `--loss`, 1 px rule baseline, 8 px minimum bar width, values labelled on the bar or at the bar end.
- **Radar:** only for the strategy comparison, 5 axes maximum, light `--rule` rings, one filled polygon per strategy at 15% opacity.
- **Do not use:** pie or donut charts, 3D, gradient fills, animated count-up numbers, dual-axis charts unless unavoidable.
- **Always provide** a text summary under each chart ("Net +₹12,480 over 18 trading days") and a "View as table" toggle.
- **Low sample:** fewer than 20 trades shows a plain note under the chart: "Based on 12 trades. Treat with caution."

## 11. Motion

- Motion only responds to a tap or to a result the person is waiting for.
- Durations: 150 ms for small changes, 220 ms for sheets, ease-out.
- **One signature moment:** after a sync finishes, the new trade rows flash `--marker` and fade to transparent over 800 ms, showing what changed.
- No entrance animations on page load, no hover lifts, no parallax, no counting numbers.
- Honour `prefers-reduced-motion`: replace the flash with a static `--marker-soft` dot beside new rows that clears on view.

## 12. Icons and imagery

- Lucide icons, 20 px in lists, 22 px in the nav, stroke 1.75.
- No emoji in the interface. No illustrations or stock photos.
- User screenshots are shown as thumbnails with radius 6, 4:3 crop in lists, uncropped in the viewer, with pinch zoom.
- App icon: a graphite square with a single `--marker` bar. PWA `theme-color` is `--chalk`.

## 13. Writing

- Sentence case. Plain verbs. Say what happens: "Connect Zerodha", "Sync now", "Save plan".
- Keep an action's name the same across the flow: the button says "Sync now", the toast says "Synced".
- Errors say what happened and what to do. Errors do not apologise.
- Empty states say what is missing and give one action.
- Never praise or scold: no "Great job!", "Oops!", "Don't give up".

| Situation | Copy |
|---|---|
| Login needed | Zerodha login needed. Today's trades import at 3:45 PM. |
| Sync done | Synced 14 fills into 6 trades. |
| Sync failed | Sync failed: Zerodha rejected the request. Try again, or connect again. |
| No trades yet | No trades yet. Sync now or import a CSV file. |
| Needs review | 3 trades need a setup and a mistake check. |
| Low sample | Based on 12 trades. Treat with caution. |
| Day over limit | Over your plan: 9 trades against a limit of 6. |

## 14. Formatting rules

- **Money:** `₹` with Indian digit grouping (`en-IN`), always signed in P&L contexts: `+₹1,23,456.50`, `−₹800.00`.
- **Compact money** where space is tight: `₹1.2k`, `₹3.4L`, `₹1.2Cr`. Use in calendar cells and axis ticks only.
- **Prices:** up to 2 decimals for equity, up to 2 for options, up to 4 only when the instrument needs it.
- **Percentages:** one decimal (`52.4%`). **Ratios:** two decimals (`1.38`). **R-multiple:** one decimal with `R` (`1.4R`).
- **Dates:** `02 Nov 2026`. **Times:** 24-hour `09:31`. **Durations:** `27m`, `1h 12m`.
- All formatting goes through one module: `apps/web/lib/format.ts`. No ad hoc formatting in components.

## 15. Accessibility

- WCAG AA contrast, checked by axe in CI.
- Visible keyboard focus: 2 px `--focus` ring with 2 px offset on every interactive element.
- Touch targets at least 44 × 44 px.
- Text scales to 200% without losing content or function.
- Screen readers: P&L values have readable labels ("minus 850 rupees"); the sync status uses `aria-live="polite"`; charts have a text summary and table view.
- Each form field has a visible label (no placeholder-only labels).
- Respect `prefers-reduced-motion`.
- Calendar is a grid with `aria-label` per day ("2 Nov 2026, net plus 2,480 rupees, 6 trades").

## 16. Implementation notes

- **Tokens.** Define the colours as CSS variables in `globals.css` and map them into Tailwind. Map shadcn's variable names to this palette so default shadcn components pick up the look automatically:

```css
:root {
  color-scheme: light;
  --chalk: #F4F6F8;  --sheet: #FFFFFF;  --fog: #EAEEF2;  --rule: #D9DFE6;
  --graphite: #1A1F26;  --slate: #55606E;
  --marker: #FFE27A;  --marker-soft: #FFF3C4;
  --profit: #0F7A55;  --profit-1: #E3F3EC;  --profit-2: #BFE3D1;  --profit-3: #8CCBAE;
  --loss: #B8322A;    --loss-1: #FBE7E4;    --loss-2: #F4C4BE;    --loss-3: #EA9A91;
  --focus: #2457D6;

  /* shadcn mapping */
  --background: var(--chalk);     --foreground: var(--graphite);
  --card: var(--sheet);           --card-foreground: var(--graphite);
  --popover: var(--sheet);        --popover-foreground: var(--graphite);
  --primary: var(--graphite);     --primary-foreground: #FFFFFF;
  --secondary: var(--fog);        --secondary-foreground: var(--graphite);
  --muted: var(--fog);            --muted-foreground: var(--slate);
  --accent: var(--marker-soft);   --accent-foreground: var(--graphite);
  --destructive: var(--loss);     --border: var(--rule);
  --input: var(--rule);           --ring: var(--focus);
  --radius: 0.625rem;             /* 10px; use 6 / 16 / 20 explicitly where specified */
}
```

- Adapt the exact syntax to the installed Tailwind and shadcn versions, but keep the token names.
- **Components.** shadcn/ui as the base, restyled to this file. Bottom sheets: shadcn Drawer (vaul). Icons: lucide-react. Charts: Recharts.
- **HTML head:** `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` and `theme-color` set to `#F4F6F8`.
- **PWA:** web app manifest and icons so it can be added to the home screen. No offline writes in version 1; a read-only cached shell is enough.
- **Forms:** react-hook-form with zod. Numeric inputs use `inputmode="decimal"`. Screenshot add button opens the photo library or camera on phones (`accept="image/*"`), and paste works on desktop.
- **Performance:** each page under 200 KB of JavaScript after gzip where possible; lazy-load charts below the fold.

## 17. Review checklist (every UI change)

- [ ] Looks right at 360, 390 and 430 px wide, then at 768 and 1280.
- [ ] Only tokens used; no raw hex, no `dark:` classes.
- [ ] No item from section 4 appears.
- [ ] Marker used only where principle 3 allows.
- [ ] Every number is formatted by `lib/format.ts`, signed, tabular, right-aligned.
- [ ] Loading, empty and error states exist.
- [ ] Touch targets 44 px or more; inputs 16 px text.
- [ ] Keyboard focus visible; axe reports no serious issues.
- [ ] Copy is sentence case, plain, and names the action.

**Self-critique prompt for the AI agent:** "Compare this screen to DESIGN.md sections 3, 4 and 17. List every place it drifts toward a generic dashboard look (card soup, decoration, default shadcn grey, all caps, arrows, emoji). Fix each one, then show a before and after list."
