"use client";

/**
 * TanStack Query hooks, one per endpoint.
 *
 * Keeping the key shapes in one file is what makes invalidation after a sync
 * or a journal save reliable: a sync touches trades, the dashboard and the
 * playbook's plan-versus-actual, and all three have to be refetched.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  Analytics,
  AnalyticsQuery,
  DashboardSummary,
  EquityCurve,
  Heatmap,
  ChannelTestResult,
  ImportProduct,
  ImportReport,
  KiteSettings,
  KiteStatus,
  NotificationChannel,
  NotificationLogEntry,
  ReminderSettings,
  ReminderSlot,
  Playbook,
  SyncLog,
  SyncStatus,
  TradeDetail,
  TradeList,
  TradePatch,
  User,
} from "@/lib/types";

export const keys = {
  me: ["me"] as const,
  kiteStatus: ["kite", "status"] as const,
  syncStatus: ["sync", "status"] as const,
  trades: (params: TradeQuery) => ["trades", params] as const,
  trade: (idOrKey: string) => ["trade", idOrKey] as const,
  summary: (from?: string, to?: string) => ["dashboard", "summary", from, to] as const,
  heatmap: (month?: string) => ["dashboard", "heatmap", month] as const,
  equityCurve: (from?: string, to?: string, by?: string) =>
    ["dashboard", "equity-curve", from, to, by] as const,
  playbook: (date: string) => ["playbook", date] as const,
  syncLogs: ["sync", "logs"] as const,
  kiteSettings: ["settings", "kite"] as const,
  reminderSettings: ["settings", "reminders"] as const,
  channel: (name: string) => ["settings", "channel", name] as const,
  notificationLog: ["settings", "notifications"] as const,
  analytics: (params: AnalyticsQuery) => ["analytics", params] as const,
};

export interface TradeQuery {
  date_from?: string;
  date_to?: string;
  product?: string[];
  asset_class?: string[];
  direction?: string;
  status?: string;
  outcome?: string;
  strategy_id?: string;
  tag_id?: string;
  q?: string;
  intraday_only?: boolean;
  needs_review?: boolean;
  sort?: string;
  order?: string;
  limit?: number;
  cursor?: string;
}

export function useMe(): UseQueryResult<User> {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api.get<User>("/auth/me"),
    retry: false,
  });
}

export function useKiteStatus(): UseQueryResult<KiteStatus> {
  return useQuery({
    queryKey: keys.kiteStatus,
    queryFn: () => api.get<KiteStatus>("/kite/status"),
    // The API caches the live check for 60 seconds; matching that here stops
    // the header asking again on every navigation.
    staleTime: 60_000,
    retry: false,
  });
}

export function useSyncStatus(): UseQueryResult<SyncStatus> {
  return useQuery({
    queryKey: keys.syncStatus,
    queryFn: () => api.get<SyncStatus>("/sync/status"),
    // Follow a running sync to its end, then stop. The catch-up sync the Kite
    // callback queues starts a beat after the redirect, so without this the
    // dashboard would sit on "not synced yet" until the next navigation.
    refetchInterval: (query) => (query.state.data?.running ? 3_000 : false),
    retry: false,
  });
}

export function useTrades(params: TradeQuery): UseQueryResult<TradeList> {
  return useQuery({
    queryKey: keys.trades(params),
    queryFn: () => api.get<TradeList>("/trades", { ...params }),
  });
}

export function useTrade(idOrKey: string | null): UseQueryResult<TradeDetail> {
  return useQuery({
    queryKey: keys.trade(idOrKey ?? ""),
    queryFn: () => api.get<TradeDetail>(`/trades/${encodeURIComponent(idOrKey ?? "")}`),
    enabled: Boolean(idOrKey),
  });
}

export function useSummary(from?: string, to?: string): UseQueryResult<DashboardSummary> {
  return useQuery({
    queryKey: keys.summary(from, to),
    queryFn: () =>
      api.get<DashboardSummary>("/dashboard/summary", { date_from: from, date_to: to }),
  });
}

export function useHeatmap(month?: string): UseQueryResult<Heatmap> {
  return useQuery({
    queryKey: keys.heatmap(month),
    queryFn: () => api.get<Heatmap>("/dashboard/heatmap", { month }),
  });
}

export function useEquityCurve(
  from?: string,
  to?: string,
  by: "day" | "trade" = "day",
): UseQueryResult<EquityCurve> {
  return useQuery({
    queryKey: keys.equityCurve(from, to, by),
    queryFn: () =>
      api.get<EquityCurve>("/dashboard/equity-curve", { date_from: from, date_to: to, by }),
  });
}

export function usePlaybook(date: string): UseQueryResult<Playbook> {
  return useQuery({
    queryKey: keys.playbook(date),
    queryFn: () => api.get<Playbook>(`/playbook/${date}`),
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api.post<User>("/auth/login", credentials),
    onSuccess: () => client.invalidateQueries(),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSuccess: () => client.clear(),
  });
}

export function useRunSync() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<SyncLog>("/sync/run"),
    onSuccess: () => {
      // A sync can change trades, every dashboard figure and the day's
      // plan-versus-actual, so everything derived from it is refetched.
      void client.invalidateQueries({ queryKey: ["trades"] });
      void client.invalidateQueries({ queryKey: ["trade"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["playbook"] });
      void client.invalidateQueries({ queryKey: keys.syncStatus });
      void client.invalidateQueries({ queryKey: keys.kiteStatus });
    },
  });
}

export function useSaveTrade(idOrKey: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: TradePatch) =>
      api.patch<TradeDetail>(`/trades/${encodeURIComponent(idOrKey)}`, patch),
    onSuccess: (detail) => {
      client.setQueryData(keys.trade(idOrKey), detail);
      void client.invalidateQueries({ queryKey: ["trades"] });
    },
  });
}

export function useSavePlaybook(date: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { plan?: unknown; review?: unknown }) =>
      api.put<Playbook>(`/playbook/${date}`, body),
    onSuccess: (playbook) => client.setQueryData(keys.playbook(date), playbook),
  });
}

/* ---------------------------------------------------------------- import */

/**
 * Parse and classify a Console tradebook without saving (FR-IMP-01).
 *
 * The response leaves `rows_new`, `rows_dup` and `unresolved_symbols` at
 * zero/empty, because `preview()` never touches the database. Do not show
 * them on the preview step.
 */
export function usePreviewTradebook() {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      // The field name is fixed by the router (routers/importer.py).
      form.append("file", file);
      return api.upload<ImportReport>("/import/tradebook/preview", form);
    },
  });
}

export function useImportTradebook() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, product }: { file: File; product?: ImportProduct }) => {
      const form = new FormData();
      form.append("file", file);
      // Omitted entirely when unset: an empty string is not a valid product
      // and the API would answer 422.
      if (product) form.append("product", product);
      return api.upload<ImportReport>("/import/tradebook", form);
    },
    onSuccess: () => {
      // An import re-runs matching, so it moves the same things a sync does,
      // minus the broker token it never touches.
      void client.invalidateQueries({ queryKey: ["trades"] });
      void client.invalidateQueries({ queryKey: ["trade"] });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["playbook"] });
      void client.invalidateQueries({ queryKey: keys.syncStatus });
    },
  });
}

/* --------------------------------------------------------------- settings */

export function useKiteSettings(): UseQueryResult<KiteSettings> {
  return useQuery({
    queryKey: keys.kiteSettings,
    queryFn: () => api.get<KiteSettings>("/settings/kite"),
    retry: false,
  });
}

export function useSaveKiteCredentials() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { api_key: string; api_secret: string }) =>
      api.put<KiteSettings>("/settings/kite", body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.kiteSettings });
      // A new key can change the connection's verdict.
      void client.invalidateQueries({ queryKey: keys.kiteStatus });
    },
  });
}

export function useReminderSettings(): UseQueryResult<ReminderSettings> {
  return useQuery({
    queryKey: keys.reminderSettings,
    queryFn: () => api.get<ReminderSettings>("/settings/reminders"),
    retry: false,
  });
}

export function useSaveReminderSlots() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (slots: ReminderSlot[]) =>
      api.put<ReminderSettings>("/settings/reminders", { slots }),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.reminderSettings }),
  });
}

export function useSkipRemindersToday() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/settings/reminders/skip-today"),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.reminderSettings }),
  });
}

export function useChannel(name: string): UseQueryResult<NotificationChannel> {
  return useQuery({
    queryKey: keys.channel(name),
    queryFn: () => api.get<NotificationChannel>(`/settings/channels/${name}`),
    retry: false,
  });
}

export function useSaveChannel(name: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { enabled: boolean; destination: string | null }) =>
      api.put<NotificationChannel>(`/settings/channels/${name}`, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.channel(name) }),
  });
}

export function useTestChannel(name: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ChannelTestResult>(`/settings/channels/${name}/test`),
    // A test writes nothing to the log, but a failure is worth re-reading.
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.notificationLog }),
  });
}

export function useNotificationLog(): UseQueryResult<NotificationLogEntry[]> {
  return useQuery({
    queryKey: keys.notificationLog,
    queryFn: () => api.get<NotificationLogEntry[]>("/settings/notifications/log", { limit: 50 }),
    retry: false,
  });
}

export function useSyncLogs(): UseQueryResult<SyncLog[]> {
  return useQuery({
    queryKey: keys.syncLogs,
    queryFn: () => api.get<SyncLog[]>("/sync/logs", { limit: 20 }),
    retry: false,
  });
}

/* -------------------------------------------------------------- analytics */

/**
 * Every breakdown on the Analytics screen, in one request (FR-AN).
 *
 * One call rather than seven: the server loads the trades once and buckets
 * them in memory, so splitting this up would re-query the same rows per
 * section over the same filters.
 */
export function useAnalytics(params: AnalyticsQuery): UseQueryResult<Analytics> {
  return useQuery({
    queryKey: keys.analytics(params),
    queryFn: () => api.get<Analytics>("/analytics", { ...params }),
  });
}
