"use client";

import { ArrowUp, ArrowDown, ChevronRight } from "lucide-react";

import { Pnl } from "@/components/common/money";
import { formatDuration, formatTime } from "@/lib/format";
import type { TradeListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  Design spec §10.1 Section E:
  Rich trade rows with symbol, side pill, time bar, qty, duration,
  product tag, large mono P&L with colour + glow, thin 3px left edge bar.
  Hover: glass-2 background, left bar widens, row shifts 2px right.
*/
export function TradeRow({
  trade,
  onOpen,
  isNew,
}: {
  trade: TradeListItem;
  onOpen: (trade: TradeListItem) => void;
  isNew?: boolean;
}) {
  const open = trade.status === "open";
  const isLong = trade.direction === "LONG";
  const pnlNum = Number(trade.net_pnl);
  const isProfit = pnlNum > 0;
  const isLoss = pnlNum < 0;

  return (
    <button
      type="button"
      onClick={() => onOpen(trade)}
      className={cn(
        "group relative flex w-full flex-col gap-2 border-b border-glass-border/60 p-4 text-left transition-all duration-200 select-none",
        "hover:bg-glass-2 hover:pl-5",
        isNew && "flash-new",
      )}
    >
      {/* 3px left edge bar in emerald / rose that widens on hover */}
      <div
        className={cn(
          "absolute left-0 top-0 bottom-0 w-[3px] transition-all duration-200 group-hover:w-[5px]",
          isProfit ? "bg-profit shadow-[0_0_8px_rgba(52,211,153,0.5)]" : isLoss ? "bg-loss shadow-[0_0_8px_rgba(251,113,133,0.5)]" : "bg-glass-border",
        )}
      />

      {/* Row content */}
      <div className="flex items-center justify-between gap-4">
        {/* Symbol + Direction Pill */}
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-body font-bold text-text-0 tracking-tight">
            {trade.tradingsymbol}
          </span>

          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider",
              isLong
                ? "bg-profit-bg border border-profit/30 text-profit"
                : "bg-loss-bg border border-loss/30 text-loss",
            )}
          >
            {isLong ? <ArrowUp size={12} strokeWidth={2.5} /> : <ArrowDown size={12} strokeWidth={2.5} />}
            {isLong ? "Long" : "Short"}
          </span>

          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold text-violet-300">
            {trade.product}
          </span>
        </div>

        {/* P&L on Right */}
        <div className="flex items-center gap-2">
          {open ? (
            <span className="rounded-full bg-warn-bg border border-warn/40 px-2.5 py-0.5 text-caption font-semibold text-warn">
              Open
            </span>
          ) : (
            <Pnl
              value={trade.net_pnl}
              glow={true}
              className="font-mono text-mono-lg font-bold"
            />
          )}
          <ChevronRight
            size={18}
            className="text-text-2 opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-1"
          />
        </div>
      </div>

      {/* Line 2: Details metadata */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-text-2">
        <span className="font-mono tabular">
          {formatTime(trade.opened_at)}
          {trade.closed_at ? ` → ${formatTime(trade.closed_at)}` : ""}
        </span>
        <span className="font-mono tabular">{trade.qty_max} qty</span>
        {trade.hold_seconds !== null && (
          <span className="rounded-[6px] bg-glass-1 px-1.5 py-0.5 font-mono text-[11px] text-text-1">
            {formatDuration(trade.hold_seconds)}
          </span>
        )}
        {trade.tags.slice(0, 2).map((tag) => (
          <span key={tag.id} className="text-text-1">
            #{tag.name}
          </span>
        ))}
      </div>
    </button>
  );
}
