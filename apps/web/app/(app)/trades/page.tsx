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

/*
  SCREENS.md 4 and 5. Rows on phones, a filter bar that sticks under the
  header, and a totals line for the filtered set. Opening a row slides the
  detail panel in rather than navigating away, so tagging a run of trades
  does not lose your place in the list.
*/

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
    <div className="flex flex-col gap-4">
      <div className="sticky top-0 z-10 -mx-4 flex flex-col gap-3 border-b border-rule
        bg-chalk px-4 pb-3 md:-mx-6 md:px-6">
        <div className="relative">
          <Search
            size={18}
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search symbol"
            aria-label="Search symbol"
            className="h-12 w-full rounded-[6px] border border-rule bg-sheet pr-3 pl-10
              text-body text-graphite placeholder:text-slate/70"
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

          <Button variant="quiet" size="icon" aria-label="More filters" disabled>
            <SlidersHorizontal size={20} aria-hidden />
          </Button>
        </div>
      </div>

      {trades.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : trades.isError ? (
        <ErrorState
          message="Could not load trades."
          onRetry={() => void trades.refetch()}
        />
      ) : trades.data && trades.data.items.length > 0 ? (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1
            border-b border-rule pb-3">
            <span className="text-secondary text-slate">
              {trades.data.totals.trades}{" "}
              {trades.data.totals.trades === 1 ? "trade" : "trades"}
            </span>
            <span className="flex flex-wrap gap-x-6 gap-y-1 text-secondary text-slate">
              <span>
                Charges <Amount value={trades.data.totals.charges} className="text-graphite" />
              </span>
              <span>
                Net <Pnl value={trades.data.totals.net_pnl} />
              </span>
            </span>
          </div>

          <div className="overflow-hidden rounded-[6px] border border-rule bg-sheet">
            {trades.data.items.map((trade) => (
              <TradeRow key={trade.group_key} trade={trade} onOpen={() => setOpen(trade.group_key)} />
            ))}
          </div>

          {trades.data.next_cursor && (
            <p className="py-2 text-center text-secondary text-slate">
              Showing the first {trades.data.items.length} of{" "}
              {trades.data.totals.trades}.
            </p>
          )}
        </>
      ) : (
        <EmptyState message="No trades match these filters." />
      )}

      <TradeDrawer idOrKey={open} onClose={() => setOpen(null)} />
    </div>
  );
}

export default function TradesPage() {
  // useSearchParams needs a boundary so the shell can still be prerendered.
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <TradesContent />
    </Suspense>
  );
}
