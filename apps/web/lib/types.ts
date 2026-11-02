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

/* ---------------------------------------------------------------- Kite */

export interface KiteLoginUrl {
  login_url: string;
  /** Shown so it can be registered in the Kite Developer Console (FR-KITE-09). */
  redirect_url: string;
}

/* -------------------------------------------------------------- Import */

export type ImportProduct = "MIS" | "CNC" | "NRML";

export interface ImportRejection {
  row: number;
  reason: string;
}

/**
 * A row of `ImportReport.preview`. The shape is fixed by the service
 * (services/importer.py), not by the CSV's own columns.
 */
export interface ImportPreviewRow {
  trade_date: string;
  symbol: string;
  exchange: string;
  side: string;
  quantity: number;
  /** A string: money never becomes a JS number before display. */
  price: string;
  product: string;
  trade_id: string;
}

/**
 * Mirrors ImportReportOut (schemas/importer.py).
 *
 * NOTE: `preview()` writes nothing to the database, so on a PREVIEW response
 * `rows_new`, `rows_dup` and `unresolved_symbols` are always 0/empty — they
 * are filled only by an actual import. Do not render them on the preview step.
 */
export interface ImportReport {
  batch_id: string | null;
  rows_read: number;
  rows_new: number;
  rows_dup: number;
  rows_rejected: number;
  date_from: string | null;
  date_to: string | null;
  columns: string[];
  symbols: string[];
  products: Record<string, number>;
  unresolved_symbols: string[];
  rows_without_timestamp: number;
  reassigned_trade_ids: number;
  rejections: ImportRejection[];
  preview: ImportPreviewRow[];
}

/* ------------------------------------------------------------- settings */

export interface KiteSettings {
  api_key_masked: string | null;
  has_secret: boolean;
  /** Register this in the Kite Developer Console (FR-KITE-09). */
  redirect_url: string;
}

export interface ReminderSlot {
  name: string;
  /** "HH:MM" in IST. */
  time: string;
  kind: "reminder" | "missed_sync";
  enabled: boolean;
}

export interface ReminderSettings {
  slots: ReminderSlot[];
  sync_time_ist: string;
  grace_minutes: number;
  quiet_hours_start_ist: string;
  quiet_hours_end_ist: string;
  skipped_today: boolean;
}

export interface NotificationChannel {
  channel: string;
  enabled: boolean;
  destination: string | null;
  configured: boolean;
  updated_at: string | null;
}

export interface ChannelTestResult {
  sent: boolean;
  destination: string | null;
  error: string | null;
}

export interface NotificationLogEntry {
  id: number;
  slot_key: string;
  channel: string;
  kind: string;
  status: string;
  attempts: number;
  scheduled_for: string | null;
  sent_at: string | null;
  error: string | null;
}

/* ------------------------------------------------------------ analytics */

export interface BucketKpis {
  trades: number;
  wins: number;
  losses: number;
  net_pnl: string;
  gross_pnl: string;
  charges: string;
  win_rate: string | null;
  profit_factor: string | null;
  expectancy: string | null;
  avg_r: string | null;
  avg_win: string | null;
  avg_loss: string | null;
  /** FR-AN-08: fewer than 20 trades is not a conclusion. */
  low_sample: boolean;
}

export interface AnalyticsBucket {
  label: string;
  kpis: BucketKpis;
}

export interface HeatCell {
  weekday: string;
  hour: number;
  trades: number;
  net_pnl: string;
}

export interface RHistogramBin {
  label: string;
  trades: number;
}

export interface RiskReport {
  net_pnl: string;
  max_drawdown: string;
  drawdown_from: string | null;
  drawdown_to: string | null;
  longest_losing_streak: number;
  longest_winning_streak: number;
  largest_win: string | null;
  largest_loss: string | null;
  trades_total: number;
  trades_with_stop: number;
  avg_planned_risk: string | null;
  r_histogram: RHistogramBin[];
  low_sample: boolean;
}

export interface MistakeCost {
  tag: string;
  trades: number;
  share_of_trades: string;
  net_pnl: string;
  avg_net_pnl: string;
}

export interface Analytics {
  date_from: string;
  date_to: string;
  trades: number;
  low_sample: boolean;
  by_strategy: AnalyticsBucket[];
  by_hour: AnalyticsBucket[];
  by_weekday: AnalyticsBucket[];
  heatmap: HeatCell[];
  by_duration: AnalyticsBucket[];
  risk: RiskReport | null;
  mistakes: MistakeCost[];
}

export interface AnalyticsQuery {
  date_from?: string;
  date_to?: string;
  asset_class?: string[];
  product?: string[];
  intraday_only?: boolean;
}
