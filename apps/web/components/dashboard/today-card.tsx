"use client";

import { useEffect } from "react";
import { ArrowUpRight, ArrowDownRight, RefreshCw, BarChart2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney, formatPercent, formatRatio } from "@/lib/format";
import { celebrateOnce } from "@/lib/motion";
import type { DashboardSummary, SyncStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

function monthLabel(month: string): string {
  const [year, index] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(
    new Date(year, index - 1, 1),
  );
}

/*
  Design spec §10.1 Section B:
  Month summary + KPI strip tiles.
  Hero Net P&L tile spans 2 cols with large mono figure and glow.
  Win rate, Profit factor, Avg win/loss, Trades count.
  Never contradicts recent trades: explains if 0 closed trades in this month.
  Triggers celebratory confetti once per day on positive net P&L.
*/
export function TodayCard({
  data,
  sync,
  isLoading,
  month,
  onSync,
}: {
  data: DashboardSummary | undefined;
  sync?: SyncStatus | undefined;
  isLoading: boolean;
  month: string;
  onSync?: () => void;
}) {
  useEffect(() => {
    if (data && Number(data.net_pnl) > 0) {
      // Confetti trigger 1: Green day / month positive reveal (spec §11.6)
      celebrateOnce(`green-summary-${month}`);
    }
  }, [data, month]);

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <Skeleton className="h-36 sm:col-span-2 lg:col-span-2 rounded-[20px]" />
        <Skeleton className="h-36 lg:col-span-1 rounded-[20px]" />
        <Skeleton className="h-36 lg:col-span-1 rounded-[20px]" />
        <Skeleton className="h-36 lg:col-span-1 rounded-[20px]" />
        <Skeleton className="h-36 lg:col-span-1 rounded-[20px]" />
      </div>
    );
  }

  const isEmpty = !data || data.trades === 0;
  const netPnlNum = data ? Number(data.net_pnl) : 0;
  const isProfit = netPnlNum > 0;
  const isLoss = netPnlNum < 0;

  return (
    <div className="flex flex-col gap-4">
      {/* KPI Tiles Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {/* Net P&L Hero Tile (spans 2 cols) */}
        <div
          className={cn(
            "glass glass--interactive relative flex flex-col justify-between overflow-hidden p-6 sm:col-span-2 lg:col-span-2",
            isProfit && "shadow-[0_0_32px_-8px_rgba(52,211,153,0.2)]",
            isLoss && "shadow-[0_0_32px_-8px_rgba(251,113,133,0.2)]",
          )}
        >
          {/* Subtle colored accent gradient behind the hero card */}
          {isProfit && (
            <div className="pointer-events-none absolute -right-12 -top-12 size-36 rounded-full bg-profit/15 blur-2xl" />
          )}
          {isLoss && (
            <div className="pointer-events-none absolute -right-12 -top-12 size-36 rounded-full bg-loss/15 blur-2xl" />
          )}

          <div className="flex items-center justify-between">
            <span className="text-label uppercase tracking-wider text-text-2">
              Net P&L · {monthLabel(month)}
            </span>
            <div
              className={cn(
                "flex size-8 items-center justify-center rounded-full border",
                isProfit
                  ? "border-profit/40 bg-profit-bg text-profit"
                  : isLoss
                    ? "border-loss/40 bg-loss-bg text-loss"
                    : "border-glass-border bg-glass-1 text-text-2",
              )}
            >
              {isProfit ? (
                <ArrowUpRight size={18} />
              ) : isLoss ? (
                <ArrowDownRight size={18} />
              ) : (
                <BarChart2 size={16} />
              )}
            </div>
          </div>

          <div className="mt-4">
            <div
              className={cn(
                "font-mono text-display font-bold tracking-tight tabular",
                isProfit && "text-profit glow-profit",
                isLoss && "text-loss glow-loss",
                !isProfit && !isLoss && "text-text-1",
              )}
            >
              {isEmpty ? "—" : formatMoney(data.net_pnl, { signed: true })}
            </div>
            <p className="mt-1 text-caption text-text-2">
              {isEmpty
                ? "No closed trades recorded this month"
                : `${data.trades} ${data.trades === 1 ? "trade" : "trades"} · ${data.wins} won · ${data.losses} lost`}
            </p>
            {sync && !sync.synced_today && (
              <p className="mt-1 text-[11px] text-warn">Today is not synced yet.</p>
            )}
          </div>
        </div>

        {/* Win Rate Tile */}
        <div className="glass glass--interactive flex flex-col justify-between p-5 lg:col-span-1">
          <span className="text-label uppercase tracking-wider text-text-2">
            Win rate
          </span>
          <div className="mt-3">
            <div className="font-mono text-h1 font-bold text-text-0 tabular">
              {isEmpty || !data.win_rate ? "—" : formatPercent(data.win_rate)}
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-glass-2">
              <div
                className="h-full rounded-full bg-violet-400"
                style={{
                  width: data?.win_rate ? `${Math.min(Number(data.win_rate) * 100, 100)}%` : "0%",
                }}
              />
            </div>
          </div>
        </div>

        {/* Profit Factor Tile */}
        <div className="glass glass--interactive flex flex-col justify-between p-5 lg:col-span-1">
          <span className="text-label uppercase tracking-wider text-text-2">
            Profit factor
          </span>
          <div className="mt-3">
            <div className="font-mono text-h1 font-bold text-text-0 tabular">
              {isEmpty || !data.profit_factor ? "—" : formatRatio(data.profit_factor)}
            </div>
            <span className="text-caption text-text-2">Gross win / loss</span>
          </div>
        </div>

        {/* Avg Win / Loss Tile */}
        <div className="glass glass--interactive flex flex-col justify-between p-5 lg:col-span-1">
          <span className="text-label uppercase tracking-wider text-text-2">
            Avg win / loss
          </span>
          <div className="mt-3 flex flex-col gap-1">
            <div className="flex items-baseline justify-between font-mono text-caption">
              <span className="text-profit">
                {isEmpty || !data.avg_win ? "—" : formatMoney(data.avg_win)}
              </span>
              <span className="text-loss">
                {isEmpty || !data.avg_loss ? "—" : formatMoney(data.avg_loss)}
              </span>
            </div>
            <span className="text-caption text-text-2">Per trade average</span>
          </div>
        </div>

        {/* Total Trades Tile */}
        <div className="glass glass--interactive flex flex-col justify-between p-5 lg:col-span-1">
          <span className="text-label uppercase tracking-wider text-text-2">
            Total trades
          </span>
          <div className="mt-3">
            <div className="font-mono text-h1 font-bold text-text-0 tabular">
              {isEmpty ? "0" : data.trades}
            </div>
            <span className="text-caption text-text-2">In {monthLabel(month)}</span>
          </div>
        </div>
      </div>

      {/* Explanatory banner for empty month to avoid audit #3 confusion */}
      {isEmpty && (
        <div className="glass flex flex-wrap items-center justify-between gap-3 border-violet-500/20 bg-violet-950/20 px-5 py-3.5">
          <p className="text-body text-text-1">
            No closed trades in {monthLabel(month)} yet. Step back a month or sync to bring today in.
          </p>
          {onSync && (
            <Button variant="secondary" size="sm" onClick={onSync} className="gap-2">
              <RefreshCw size={14} />
              Sync now
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
