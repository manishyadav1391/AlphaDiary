/**
 * Every number on screen goes through this module (DESIGN.md 14).
 *
 * The API sends money as plain decimal strings — "12480.50", never
 * "₹12,480.50" — so grouping, the rupee sign and the sign itself are decided
 * here and nowhere else. Formatting in components is what makes two screens
 * disagree about the same number.
 *
 * Amounts are parsed with `Number` only at the point of display. The arithmetic
 * that matters already happened in Python with Decimal; nothing here adds,
 * subtracts or compares money.
 */

/** U+2212, the real minus sign. A hyphen is not a minus (DESIGN.md 6). */
const MINUS = "−";
const RUPEE = "₹";

const groupedTwoDp = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const groupedWhole = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 0,
});

export type Money = string | number | null | undefined;

function toNumber(value: Money): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** The placeholder for a value that does not exist (DESIGN.md: "–"). */
export const EMPTY = "–";

/**
 * `₹1,23,456.50`. Pass `signed` in a P&L context, where the sign carries
 * meaning and must never be left to colour alone (DESIGN.md 5).
 */
export function formatMoney(value: Money, options: { signed?: boolean } = {}): string {
  const amount = toNumber(value);
  if (amount === null) return EMPTY;

  const body = `${RUPEE}${groupedTwoDp.format(Math.abs(amount))}`;
  if (amount < 0) return `${MINUS}${body}`;
  return options.signed ? `+${body}` : body;
}

/**
 * Compact money for calendar cells and axis ticks only (DESIGN.md 14).
 * `₹1.2k`, `₹3.4L`, `₹1.2Cr`.
 */
export function formatMoneyCompact(value: Money, options: { signed?: boolean } = {}): string {
  const amount = toNumber(value);
  if (amount === null) return EMPTY;

  const magnitude = Math.abs(amount);
  let body: string;
  if (magnitude >= 10_000_000) {
    body = `${RUPEE}${trim(magnitude / 10_000_000)}Cr`;
  } else if (magnitude >= 100_000) {
    body = `${RUPEE}${trim(magnitude / 100_000)}L`;
  } else if (magnitude >= 1_000) {
    body = `${RUPEE}${trim(magnitude / 1_000)}k`;
  } else {
    body = `${RUPEE}${groupedWhole.format(magnitude)}`;
  }

  if (amount < 0) return `${MINUS}${body}`;
  return options.signed ? `+${body}` : body;
}

function trim(value: number): string {
  // One decimal, but 1.0k reads worse than 1k.
  const fixed = value.toFixed(1);
  return fixed.endsWith(".0") ? fixed.slice(0, -2) : fixed;
}

/** Prices: up to 2 decimals, 4 only when the instrument needs them. */
export function formatPrice(value: Money, decimals: 2 | 4 = 2): string {
  const amount = toNumber(value);
  if (amount === null) return EMPTY;
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  }).format(amount);
}

/** Percentages carry one decimal: `52.4%`. Input is a ratio, so 0.524. */
export function formatPercent(ratio: Money): string {
  const value = toNumber(ratio);
  if (value === null) return EMPTY;
  return `${(value * 100).toFixed(1)}%`;
}

/** Ratios carry two decimals: `1.38`. */
export function formatRatio(value: Money): string {
  const parsed = toNumber(value);
  if (parsed === null) return EMPTY;
  return parsed.toFixed(2);
}

/** R-multiples carry one decimal and the letter: `1.4R`, `−0.8R`. */
export function formatR(value: Money): string {
  const parsed = toNumber(value);
  if (parsed === null) return EMPTY;
  const body = `${Math.abs(parsed).toFixed(1)}R`;
  return parsed < 0 ? `${MINUS}${body}` : body;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY;
  return groupedWhole.format(value);
}

/** `02 Nov 2026`. */
export function formatDate(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: IST,
  }).format(date);
}

/** `02 Nov`, for axis ticks and dense rows. */
export function formatDateShort(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    timeZone: IST,
  }).format(date);
}

/**
 * `09:31`, 24-hour, always in IST.
 *
 * The API sends UTC with an offset; trading days and clock times belong to
 * Asia/Kolkata, so the zone is pinned rather than left to the browser.
 */
export function formatTime(value: string | Date | null | undefined): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: IST,
  }).format(date);
}

const IST = "Asia/Kolkata";

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Durations: `27m`, `1h 12m`, `2d 3h`. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return EMPTY;
  if (seconds < 60) return `${Math.round(seconds)}s`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;

  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (hours < 24) return restMinutes ? `${hours}h ${restMinutes}m` : `${hours}h`;

  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days}d ${restHours}h` : `${days}d`;
}

/** The ISO date (`2026-11-02`) for an IST day, for API query parameters. */
export function toIsoDate(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: IST,
  }).format(date);
}

export function sign(value: Money): "profit" | "loss" | "flat" {
  const amount = toNumber(value);
  if (amount === null || amount === 0) return "flat";
  return amount > 0 ? "profit" : "loss";
}

/**
 * A screen-reader label for a P&L figure, so it is not read as a bare number
 * with a stray symbol (DESIGN.md 15).
 */
export function moneyLabel(value: Money): string {
  const amount = toNumber(value);
  if (amount === null) return "no value";
  const words = groupedTwoDp.format(Math.abs(amount));
  if (amount === 0) return `${words} rupees`;
  return `${amount > 0 ? "plus" : "minus"} ${words} rupees`;
}
