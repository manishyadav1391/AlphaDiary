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
  DashboardSummary,
  EquityCurve,
  Heatmap,
  KiteStatus,
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
