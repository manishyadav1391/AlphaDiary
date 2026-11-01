"use client";

import { Pnl } from "@/components/common/money";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary, SyncStatus } from "@/lib/types";

function monthLabel(month: string): string {
  const [year, index] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(
    new Date(year, index - 1, 1),
  );
}

/**
 * The one card on Home (DESIGN.md 9): white, radius 16, 1 px rule border.
 * It holds the single display figure and a short line of counts.
 */
export function TodayCard({
  data,
  sync,
  isLoading,
  month,
}: {
  data: DashboardSummary | undefined;
  sync: SyncStatus | undefined;
  isLoading: boolean;
  month: string;
}) {
  if (isLoading) return <Skeleton className="h-36 w-full rounded-[16px]" />;
  if (!data) return null;

  if (data.trades === 0) {
    return (
      <div className="flex flex-col gap-2 rounded-[16px] border border-rule bg-sheet p-4">
        <p className="text-secondary text-slate">{monthLabel(month)}</p>
        <p className="text-body text-graphite">No closed trades this month.</p>
        <p className="text-secondary text-slate">
          Step back a month, or sync to bring today in.
        </p>
      </div>
    );
  }

  const counts = [
    `${data.trades} ${data.trades === 1 ? "trade" : "trades"}`,
    `${data.wins} won`,
    `${data.losses} lost`,
  ].join("   ");

  return (
    <div className="flex flex-col gap-2 rounded-[16px] border border-rule bg-sheet p-4">
      <p className="text-secondary text-slate">Net in {monthLabel(month)}</p>
      <Pnl value={data.net_pnl} className="text-display" />
      <p className="text-secondary text-slate">{counts}</p>
      {sync && !sync.synced_today && (
        <p className="text-secondary text-slate">Today is not synced yet.</p>
      )}
    </div>
  );
}
