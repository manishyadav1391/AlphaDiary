"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Check } from "lucide-react";

import { Amount, Pnl } from "@/components/common/money";
import { PlanForm, ReviewForm } from "@/components/playbook/forms";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, toIsoDate } from "@/lib/format";
import { usePlaybook } from "@/lib/queries";
import type { PlanVersusActual } from "@/lib/types";
import { cn } from "@/lib/utils";

function PlanVersusActualCard({ actual }: { actual: PlanVersusActual }) {
  const broken = actual.trades_limit_broken || actual.loss_limit_broken;

  return (
    <div className="glass flex flex-col gap-3 p-6 md:p-8">
      <h3 className="text-h3 font-bold text-text-0">Today&apos;s Risk vs Plan</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-[12px] bg-glass-1 border border-glass-border p-3.5">
          <span className="text-label uppercase tracking-wider text-text-2">Trades</span>
          <div className="mt-1 font-mono text-h3 font-bold text-text-0 tabular">
            {actual.trades_taken}
            {actual.max_trades !== null ? ` / ${actual.max_trades}` : ""}
          </div>
        </div>

        <div className="rounded-[12px] bg-glass-1 border border-glass-border p-3.5">
          <span className="text-label uppercase tracking-wider text-text-2">Net P&L</span>
          <div className="mt-1">
            <Pnl value={actual.net_pnl} className="font-mono text-h3 font-bold" />
          </div>
        </div>

        {actual.max_loss !== null && (
          <div className="rounded-[12px] bg-glass-1 border border-glass-border p-3.5">
            <span className="text-label uppercase tracking-wider text-text-2">Max loss limit</span>
            <div className="mt-1">
              <Amount value={actual.max_loss} className="font-mono text-h3 font-bold" />
            </div>
          </div>
        )}
      </div>

      {broken && (
        <div className="rounded-[12px] border border-loss/40 bg-loss-bg/30 p-3.5 text-body text-loss">
          {actual.trades_limit_broken
            ? `Limit exceeded: ${actual.trades_taken} trades taken against limit of ${actual.max_trades}.`
            : "Limit exceeded: day's loss crossed the planned maximum loss limit."}
        </div>
      )}
    </div>
  );
}

export default function PlaybookPage() {
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const dateIso = toIsoDate(currentDate);
  const playbook = usePlaybook(dateIso);

  const shiftDay = (days: number) => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + days);
      return next;
    });
  };

  const isToday = toIsoDate(currentDate) === toIsoDate(new Date());

  const planDone = Boolean(playbook.data?.plan);
  const reviewDone = Boolean(playbook.data?.review);

  return (
    <div className="mx-auto flex max-w-[820px] flex-col gap-8">
      {/* Page Header with Day Navigation */}
      <div className="glass flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex items-center gap-3">
          <Button
            variant="quiet"
            size="icon-sm"
            onClick={() => shiftDay(-1)}
            aria-label="Previous day"
            className="size-9 rounded-full"
          >
            <ChevronLeft size={18} />
          </Button>

          <div className="flex flex-col">
            <span className="text-h2 font-bold text-text-0">{formatDate(currentDate)}</span>
            {isToday && (
              <span className="text-[11px] font-semibold uppercase tracking-wider text-violet-400">
                Today
              </span>
            )}
          </div>

          <Button
            variant="quiet"
            size="icon-sm"
            onClick={() => shiftDay(1)}
            aria-label="Next day"
            className="size-9 rounded-full"
          >
            <ChevronRight size={18} />
          </Button>
        </div>

        {/* Progress indicator: Before the open -> After the close */}
        <div className="flex items-center gap-2">
          {/* Step 1 */}
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "flex size-6 items-center justify-center rounded-full text-[11px] font-bold transition-all",
                planDone
                  ? "bg-violet-600 text-white shadow-[0_0_10px_rgba(139,92,246,0.6)]"
                  : "bg-glass-2 border border-glass-border text-text-2",
              )}
            >
              {planDone ? <Check size={12} strokeWidth={2.5} /> : "1"}
            </div>
            <span className="hidden text-caption font-medium text-text-1 sm:inline">
              Before open
            </span>
          </div>

          {/* Connecting line */}
          <div
            className={cn(
              "h-0.5 w-6 transition-all",
              planDone && reviewDone ? "bg-violet-500" : "bg-glass-border",
            )}
          />

          {/* Step 2 */}
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "flex size-6 items-center justify-center rounded-full text-[11px] font-bold transition-all",
                reviewDone
                  ? "bg-violet-600 text-white shadow-[0_0_10px_rgba(139,92,246,0.6)]"
                  : "bg-glass-2 border border-glass-border text-text-2",
              )}
            >
              {reviewDone ? <Check size={12} strokeWidth={2.5} /> : "2"}
            </div>
            <span className="hidden text-caption font-medium text-text-1 sm:inline">
              After close
            </span>
          </div>
        </div>
      </div>

      {playbook.isLoading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-64 w-full rounded-[20px]" />
          <Skeleton className="h-64 w-full rounded-[20px]" />
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {/* Card 1: Before the open */}
          <PlanForm
            key={`plan-${dateIso}`}
            date={dateIso}
            plan={playbook.data?.plan ?? null}
            actual={playbook.data?.actual}
          />

          {/* Plan versus Actual comparison if trades taken */}
          {playbook.data?.actual && playbook.data.actual.trades_taken > 0 && (
            <PlanVersusActualCard actual={playbook.data.actual} />
          )}

          {/* Card 2: After the close */}
          <ReviewForm
            key={`review-${dateIso}`}
            date={dateIso}
            review={playbook.data?.review ?? null}
          />
        </div>
      )}
    </div>
  );
}
