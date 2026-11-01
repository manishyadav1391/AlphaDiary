"use client";

import { useState } from "react";

import { Amount, Pnl } from "@/components/common/money";
import { Section } from "@/components/common/states";
import { PlanForm, ReviewForm } from "@/components/playbook/forms";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, toIsoDate } from "@/lib/format";
import { usePlaybook } from "@/lib/queries";
import type { PlanVersusActual } from "@/lib/types";

/** The daily playbook (SCREENS.md 8, FR-PB). */
function PlanVersusActualCard({ actual }: { actual: PlanVersusActual }) {
  const broken = actual.trades_limit_broken || actual.loss_limit_broken;

  return (
    <Section title="Plan versus actual">
      <div className="flex flex-col gap-2 rounded-[16px] border border-rule bg-sheet p-4">
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-secondary text-slate">Trades</span>
          <span className="tabular text-graphite">
            {actual.trades_taken}
            {actual.max_trades !== null ? ` of ${actual.max_trades}` : ""}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-secondary text-slate">Net</span>
          <Pnl value={actual.net_pnl} />
        </div>
        {actual.max_loss !== null && (
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-secondary text-slate">Loss limit</span>
            <Amount value={actual.max_loss} className="text-graphite" />
          </div>
        )}
        {broken && (
          // The marker is allowed here: this is the "needs attention" case.
          <p className="rounded-[6px] bg-marker-soft px-3 py-2 text-secondary text-graphite">
            {actual.trades_limit_broken
              ? `Over your plan: ${actual.trades_taken} trades against a limit of ${actual.max_trades}.`
              : "Over your plan: the day's loss passed your limit."}
          </p>
        )}
      </div>
    </Section>
  );
}

export default function PlaybookPage() {
  const [date] = useState(() => toIsoDate(new Date()));
  const playbook = usePlaybook(date);

  if (playbook.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-56 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const actual = playbook.data?.actual;

  return (
    <div className="flex flex-col gap-10">
      <p className="text-secondary text-slate">{formatDate(date)}</p>

      <PlanForm key={`plan-${date}`} date={date} plan={playbook.data?.plan ?? null} />

      {actual && actual.trades_taken > 0 && <PlanVersusActualCard actual={actual} />}

      <ReviewForm key={`review-${date}`} date={date} review={playbook.data?.review ?? null} />
    </div>
  );
}
