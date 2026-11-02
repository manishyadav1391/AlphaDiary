/**
 * Copy and formatting for the Zerodha connection, shared by the header chip,
 * the dashboard banner and /connect.
 *
 * Kite Connect has no refresh token: the access token dies at about 06:00 IST
 * the next morning and only a human browser login can mint a new one. So this
 * copy appears every trading day, and DESIGN.md 13 applies — say what
 * happened and what to do, never apologise.
 */

import { formatDateShort, formatTime, toIsoDate } from "@/lib/format";

/**
 * Every code `GET /api/v1/kite/callback` can redirect with
 * (routers/kite.py). Unknown codes fall through to a generic line rather
 * than showing the owner a raw slug.
 */
const KITE_ERRORS: Record<string, string> = {
  login_failed: "Zerodha did not complete the login. Connect again.",
  missing_request_token: "Zerodha sent no login token. Connect again.",
  invalid_state: "That connection link had expired. Connect again.",
  not_configured: "Add your Kite API key and secret before connecting.",
  token_rejected: "Zerodha rejected the login token. Connect again.",
  exchange_failed: "Could not reach Zerodha to finish the login. Try again.",
};

export function kiteErrorMessage(code: string | null | undefined): string {
  if (!code) return "The Zerodha connection did not finish. Connect again.";
  return KITE_ERRORS[code] ?? "The Zerodha connection did not finish. Connect again.";
}

/** The standing banner line while the token is dead (DESIGN.md 13). */
export const LOGIN_NEEDED = "Zerodha login needed. Today's trades import at 3:45 PM.";

/**
 * `Expires 06:00`, or `Expires 03 Nov 06:00` once it crosses into tomorrow.
 *
 * An estimate: `token_valid_until` is the next 06:00 IST written at login, and
 * the live profile() call is the real answer (FR-KITE-04). Returns null when
 * the column was never written, so the caller can render the label alone
 * rather than printing an em dash.
 */
export function expiryLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;

  const sameIstDay = toIsoDate(date) === toIsoDate(new Date());
  return sameIstDay
    ? `Expires ${formatTime(date)}`
    : `Expires ${formatDateShort(date)} ${formatTime(date)}`;
}
