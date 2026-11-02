"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { EMPTY, formatMoney, formatPercent, formatR, formatRatio } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

/**
 * A horizontally scrollable row of compact metrics, divided by rules with no
 * boxes (DESIGN.md 9). A missing value shows a dash rather than a zero, since
 * "no losing trades yet" and "profit factor of nought" are different things.
 */
export function MetricStrip({
  data,
  isLoading,
}: {
  data: DashboardSummary | undefined;
  isLoading: boolean;
}) {
  if (isLoading) return <Skeleton className="h-16 w-full" />;
  if (!data) return null;

  const metrics = [
    { label: "Win rate", value: data.win_rate ? formatPercent(data.win_rate) : EMPTY },
    { label: "Profit factor", value: data.profit_factor ? formatRatio(data.profit_factor) : EMPTY },
    { label: "Expectancy", value: data.expectancy ? formatMoney(data.expectancy, { signed: true }) : EMPTY },
    { label: "Average R", value: data.avg_r ? formatR(data.avg_r) : EMPTY },
    { label: "Max drawdown", value: formatMoney(data.max_drawdown) },
    { label: "Trades", value: String(data.trades) },
  ];

  return (
    <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
      <dl className="flex min-w-max divide-x divide-rule">
        {metrics.map((metric) => (
          <div key={metric.label} className="flex flex-col gap-1 px-4 first:pl-0 last:pr-0">
            <dt className="text-caption text-text-2">{metric.label}</dt>
            <dd className="text-mono-sm text-text-0">{metric.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
