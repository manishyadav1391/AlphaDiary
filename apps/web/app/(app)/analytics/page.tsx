"use client";

import { useState } from "react";

import { HourHeatmap } from "@/components/analytics/hour-heatmap";
import { MistakeTable } from "@/components/analytics/mistake-table";
import { PnlBars } from "@/components/analytics/pnl-bars";
import { RiskPanel } from "@/components/analytics/risk-panel";
import { LowSampleNote } from "@/components/common/low-sample";
import { EmptyState, ErrorState, Section } from "@/components/common/states";
import { MonthPicker, currentMonth, monthRange } from "@/components/dashboard/month-picker";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalytics } from "@/lib/queries";
import { formatCount } from "@/lib/format";

/*
  FR-AN. Strategy, time edge, duration, risk and mistake cost over one set of
  filters.

  Every section reads the same response: the server loads the trades once and
  buckets them, so changing a filter is a single request rather than seven.
*/

const PRODUCTS = ["MIS", "CNC", "NRML"] as const;

export default function AnalyticsPage() {
  const [month, setMonth] = useState(currentMonth());
  const [product, setProduct] = useState<string[]>([]);
  const [intradayOnly, setIntradayOnly] = useState(false);

  const { from, to } = monthRange(month);
  const analytics = useAnalytics({
    date_from: from,
    date_to: to,
    product,
    intraday_only: intradayOnly,
  });

  function toggleProduct(value: string) {
    setProduct((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  }

  const data = analytics.data;

  return (
    <div className="flex flex-col gap-8">
      {/* Filters in one row above the charts. */}
      <div className="flex flex-wrap items-center gap-3">
        <MonthPicker month={month} onChange={setMonth} />

        <div className="flex flex-wrap items-center gap-1.5">
          {PRODUCTS.map((value) => (
            <button key={value} type="button" onClick={() => toggleProduct(value)}>
              <Chip tone={product.includes(value) ? "selected" : "default"}>{value}</Chip>
            </button>
          ))}
          <button type="button" onClick={() => setIntradayOnly((current) => !current)}>
            <Chip tone={intradayOnly ? "selected" : "default"}>Intraday only</Chip>
          </button>
        </div>

        {data && (
          <span className="ml-auto text-caption text-text-2">
            {formatCount(data.trades)} closed trades
          </span>
        )}
      </div>

      {analytics.isLoading && (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-64 w-full rounded-[16px]" />
          <Skeleton className="h-64 w-full rounded-[16px]" />
        </div>
      )}

      {analytics.isError && (
        <ErrorState
          message="Could not load analytics."
          onRetry={() => void analytics.refetch()}
        />
      )}

      {data && data.trades === 0 && (
        <EmptyState message="No closed trades in this range. Analytics appear once trades are matched." />
      )}

      {data && data.trades > 0 && (
        <>
          {/* FR-AN-08: say so once, at the top, rather than on every chart. */}
          {data.low_sample && <LowSampleNote trades={data.trades} />}

          <Section title="Strategy">
            <PnlBars buckets={data.by_strategy} angledLabels />
          </Section>

          <Section title="Time of day">
            <PnlBars buckets={data.by_hour} />
          </Section>

          <Section title="Day of week">
            <PnlBars buckets={data.by_weekday} />
          </Section>

          <Section title="Hour by weekday">
            <HourHeatmap cells={data.heatmap} />
          </Section>

          <Section title="Holding duration">
            <PnlBars buckets={data.by_duration} />
          </Section>

          {data.risk && (
            <Section title="Risk">
              <RiskPanel risk={data.risk} />
            </Section>
          )}

          <Section title="Mistake cost">
            <MistakeTable rows={data.mistakes} />
          </Section>
        </>
      )}
    </div>
  );
}
