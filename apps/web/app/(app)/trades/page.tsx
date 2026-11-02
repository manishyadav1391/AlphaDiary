"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Amount, Pnl } from "@/components/common/money";
import { EmptyState, ErrorState } from "@/components/common/states";
import { TradeDrawer } from "@/components/trades/trade-drawer";
import { TradeRow } from "@/components/trades/trade-row";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { useTrades, type TradeQuery } from "@/lib/queries";

const OUTCOMES = [
  { value: undefined, label: "All" },
  { value: "win", label: "Wins" },
  { value: "loss", label: "Losses" },
] as const;

function TradesContent() {
  const params = useSearchParams();
  const [search, setSearch] = useState("");
  const [outcome, setOutcome] = useState<string | undefined>(undefined);
  const [intradayOnly, setIntradayOnly] = useState(true);
  const [needsReview, setNeedsReview] = useState(false);
  const [open, setOpen] = useState<string | null>(params.get("open"));

  const query: TradeQuery = {
    date_from: params.get("date_from") ?? undefined,
    date_to: params.get("date_to") ?? undefined,
    q: search || undefined,
    outcome,
    intraday_only: intradayOnly,
    needs_review: needsReview || undefined,
    limit: 50,
  };

  const trades = useTrades(query);

  return (
    <div className="flex flex-col gap-6">
      {/* Sticky Filter Bar (Glass) */}
      <div className="glass sticky top-16 z-10 flex flex-col gap-3.5 p-4 shadow-lg backdrop-blur-xl">
        <div className="relative">
          <Search
            size={18}
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-text-2"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search symbol (e.g. NIFTY, RELIANCE)"
            aria-label="Search symbol"
            className="h-11 w-full rounded-[12px] border border-glass-border bg-glass-1 pr-4 pl-10 text-body text-text-0 placeholder:text-text-2 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-400/40"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {OUTCOMES.map((option) => (
            <button
              key={option.label}
              type="button"
              onClick={() => setOutcome(option.value)}
              aria-pressed={outcome === option.value}
            >
              <Chip tone={outcome === option.value ? "selected" : "default"}>
                {option.label}
              </Chip>
            </button>
          ))}

          <button
            type="button"
            onClick={() => setIntradayOnly((value) => !value)}
            aria-pressed={intradayOnly}
          >
            <Chip tone={intradayOnly ? "selected" : "default"}>Intraday only</Chip>
          </button>

          <button
            type="button"
            onClick={() => setNeedsReview((value) => !value)}
            aria-pressed={needsReview}
          >
            <Chip tone={needsReview ? "marker" : "default"}>Needs review</Chip>
          </button>

          <Button
            variant="quiet"
            size="icon-sm"
            aria-label="More filters"
            disabled
            className="ml-auto"
          >
            <SlidersHorizontal size={18} aria-hidden />
          </Button>
        </div>
      </div>

      {/* Trades List View */}
      {trades.isLoading ? (
        <Skeleton className="h-96 w-full rounded-[20px]" />
      ) : trades.isError ? (
        <ErrorState
          message="Could not load trades from server."
          onRetry={() => void trades.refetch()}
        />
      ) : trades.data && trades.data.items.length > 0 ? (
        <>
          {/* Totals Strip */}
          <div className="glass flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-5 py-3 rounded-[14px]">
            <span className="text-body font-semibold text-text-0">
              {trades.data.totals.trades}{" "}
              {trades.data.totals.trades === 1 ? "trade" : "trades"}
            </span>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-caption text-text-2">
              <span>
                Charges:{" "}
                <Amount value={trades.data.totals.charges} className="font-bold text-text-0" />
              </span>
              <span>
                Net:{" "}
                <Pnl value={trades.data.totals.net_pnl} glow={true} className="font-bold text-body" />
              </span>
            </div>
          </div>

          {/* List Container */}
          <div className="glass overflow-hidden rounded-[20px]">
            {trades.data.items.map((trade) => (
              <TradeRow
                key={trade.group_key}
                trade={trade}
                onOpen={() => setOpen(trade.group_key)}
              />
            ))}
          </div>

          {trades.data.next_cursor && (
            <p className="py-2 text-center text-caption text-text-2">
              Showing {trades.data.items.length} of {trades.data.totals.trades} trades
            </p>
          )}
        </>
      ) : (
        <EmptyState
          title="No matching trades"
          message="Try adjusting your search or filters to see more results."
        />
      )}

      {/* Trade detail drawer */}
      <TradeDrawer idOrKey={open} onClose={() => setOpen(null)} />
    </div>
  );
}

export default function TradesPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-[20px]" />}>
      <TradesContent />
    </Suspense>
  );
}
