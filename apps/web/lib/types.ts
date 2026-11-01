/**
 * Shapes returned by the FastAPI app.
 *
 * Every monetary field is `string`, matching SRS 4.3 and the OpenAPI schema:
 * JSON numbers are doubles, and routing money through one would undo the
 * Decimal pipeline behind it. Parse only at the point of display, via
 * `lib/format.ts`.
 */

export type Direction = "LONG" | "SHORT";
export type TradeStatus = "open" | "closed";
export type Outcome = "win" | "loss" | "breakeven";
export type FollowedPlan = "yes" | "partly" | "no";
export type Bias = "bullish" | "bearish" | "neutral";

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export interface User {
  id: string;
  email: string;
}

export type KiteStatusValue = "connected" | "expired" | "not_configured" | "error";

export interface KiteStatus {
  status: KiteStatusValue;
  kite_user_id: string | null;
  api_key_masked: string | null;
  token_issued_at: string | null;
  token_valid_until: string | null;
  message: string | null;
}

export interface SyncLog {
  id: string;
  trigger: "manual" | "scheduled" | "login_catchup" | "csv";
  status: "running" | "success" | "partial" | "failed" | "skipped_no_token";
  started_at: string;
  finished_at: string | null;
  fills_new: number;
  fills_dup: number;
  fills_rejected: number;
  orders_upserted: number;
  error: string | null;
}

export interface SyncStatus {
  running: boolean;
  synced_today: boolean;
  last: SyncLog | null;
}

export interface Tag {
  id: string;
  kind: "mistake" | "attribute";
  name: string;
}

export interface TradeListItem {
  id: string;
  /** Stable across re-matching; prefer it for links (FR-MATCH-07). */
  group_key: string;
  trade_date: string;
  tradingsymbol: string;
  exchange: string;
  asset_class: string;
  product: string;
  direction: Direction;
  status: TradeStatus;
  is_intraday: boolean;
  qty_max: number;
  open_qty: number;
  avg_entry: string | null;
  avg_exit: string | null;
  opened_at: string;
  closed_at: string | null;
  hold_seconds: number | null;
  gross_pnl: string;
  charges_total: string;
  net_pnl: string;
  outcome: Outcome | null;
  strategy_id: string | null;
  tags: Tag[];
  r_multiple: string | null;
}

export interface TradeTotals {
  trades: number;
  gross_pnl: string;
  charges: string;
  net_pnl: string;
}

export interface TradeList {
  items: TradeListItem[];
  next_cursor: string | null;
  totals: TradeTotals;
  intraday_only: boolean;
}

export interface TradeFill {
  id: string;
  kite_trade_id: string;
  order_id: string | null;
  role: "entry" | "exit";
  side: "BUY" | "SELL";
  quantity: number;
  quantity_used: number;
  price: string;
  filled_at: string;
  source: string;
  charge_total: string | null;
}

export interface ChargeBreakdown {
  brokerage: string;
  stt_ctt: string;
  exchange_txn: string;
  sebi: string;
  stamp: string;
  other_levy: string;
  gst: string;
  total: string;
  segment_keys: string[];
}

export interface Journal {
  strategy_id: string | null;
  planned_entry: string | null;
  planned_sl: string | null;
  planned_target: string | null;
  entry_reason: string | null;
  exit_reason: string | null;
  emotion: string | null;
  followed_plan: FollowedPlan | null;
  execution_rating: number | null;
  lessons: string | null;
  updated_at: string | null;
}

export interface Derived {
  planned_risk_amount: string | null;
  planned_rr: string | null;
  r_multiple: string | null;
  slippage_amount: string | null;
  slippage_percent: string | null;
}

export interface TradeDetail extends TradeListItem {
  fills: TradeFill[];
  charges: ChargeBreakdown;
  journal: Journal;
  derived: Derived;
  previous_group_key: string | null;
  next_group_key: string | null;
}

export interface TradePatch {
  strategy_id?: string | null;
  planned_entry?: string | null;
  planned_sl?: string | null;
  planned_target?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  emotion?: string | null;
  followed_plan?: FollowedPlan | null;
  execution_rating?: number | null;
  lessons?: string | null;
  tag_ids?: string[];
}

export interface DashboardSummary {
  date_from: string;
  date_to: string;
  trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  gross_pnl: string;
  charges: string;
  net_pnl: string;
  win_rate: string | null;
  profit_factor: string | null;
  expectancy: string | null;
  avg_r: string | null;
  avg_win: string | null;
  avg_loss: string | null;
  largest_win: string | null;
  largest_loss: string | null;
  max_drawdown: string;
  longest_losing_streak: number;
  green_day_rate: string | null;
  low_sample: boolean;
}

export interface HeatmapDay {
  trade_date: string;
  net_pnl: string;
  trades_count: number;
  is_holiday: boolean;
}

export interface HeatmapWeek {
  week_start: string;
  net_pnl: string;
  trades_count: number;
}

export interface Heatmap {
  month: string;
  days: HeatmapDay[];
  weeks: HeatmapWeek[];
  net_pnl: string;
  trades_count: number;
  max_abs_day: string;
}

export interface CurvePoint {
  label: string;
  net_pnl: string;
  cumulative: string;
}

export interface EquityCurve {
  date_from: string;
  date_to: string;
  by: "day" | "trade";
  points: CurvePoint[];
  net_pnl: string;
}

export interface DailyPlan {
  trade_date: string;
  bias: Bias | null;
  key_levels: string | null;
  events: string | null;
  max_loss: string | null;
  max_trades: number | null;
  max_risk_per_trade: string | null;
  checklist: Record<string, boolean> | null;
  updated_at: string | null;
}

export interface DailyReview {
  trade_date: string;
  discipline_rating: number | null;
  emotion: string | null;
  went_well: string | null;
  to_improve: string | null;
  summary: string | null;
  updated_at: string | null;
}

export interface PlanVersusActual {
  trades_taken: number;
  max_trades: number | null;
  trades_limit_broken: boolean;
  net_pnl: string;
  max_loss: string | null;
  loss_limit_broken: boolean;
}

export interface Playbook {
  trade_date: string;
  plan: DailyPlan | null;
  review: DailyReview | null;
  plan_done: boolean;
  review_done: boolean;
  actual: PlanVersusActual;
}
