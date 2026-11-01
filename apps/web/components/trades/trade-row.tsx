"use client";

import { Pnl } from "@/components/common/money";
import { Chip } from "@/components/ui/chip";
import { formatDuration, formatTime } from "@/lib/format";
import type { TradeListItem } from "@/lib/types";

/*
  DESIGN.md 9, trade row. Two lines in one row on phones:
  line 1 symbol and direction, net P&L right-aligned and signed;
  line 2 times, quantity and setup as separate spans with spacing, never
  joined by middle dots. An open trade shows a chip instead of a P&L.
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

  return (
    <button
      type="button"
      onClick={() => onOpen(trade)}
      className={`flex min-h-14 w-full flex-col gap-1 border-b border-rule px-4 py-3
        text-left hover:bg-fog ${isNew ? "flash-new" : ""}`}
    >
      <span className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <span className="text-row text-graphite">{trade.tradingsymbol}</span>
          <Chip>{trade.direction === "LONG" ? "Long" : "Short"}</Chip>
        </span>
        {open ? (
          <Chip tone="marker">Open</Chip>
        ) : (
          <Pnl value={trade.net_pnl} className="font-condensed text-figure" />
        )}
      </span>

      <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-secondary text-slate">
        <span className="tabular">
          {formatTime(trade.opened_at)}
          {trade.closed_at ? ` to ${formatTime(trade.closed_at)}` : ""}
        </span>
        <span className="tabular">{trade.qty_max} qty</span>
        {trade.hold_seconds !== null && (
          <span className="tabular">{formatDuration(trade.hold_seconds)}</span>
        )}
        <span>{trade.product}</span>
        {trade.tags.slice(0, 2).map((tag) => (
          <span key={tag.id}>{tag.name}</span>
        ))}
      </span>
    </button>
  );
}
