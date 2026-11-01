"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { LowSampleNote } from "@/components/common/low-sample";
import { EmptyState, Section } from "@/components/common/states";
import { CalendarHeatmap } from "@/components/dashboard/calendar";
import { EquityCurveChart } from "@/components/dashboard/equity-curve";
import { MetricStrip } from "@/components/dashboard/metric-strip";
import {
  MonthPicker,
  currentMonth,
  monthRange,
} from "@/components/dashboard/month-picker";
import { TodayCard } from "@/components/dashboard/today-card";
import { TradeRow } from "@/components/trades/trade-row";
import { Skeleton } from "@/components/ui/skeleton";
import { useEquityCurve, useHeatmap, useSummary, useSyncStatus, useTrades } from "@/lib/queries";

/** Home (SCREENS.md 2, FR-DASH). */
function HomeContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  // The month lives in the URL so the view is bookmarkable (FR-DASH-01).
  const month = params.get("month") ?? currentMonth();
  const { from, to } = monthRange(month);

  const summary = useSummary(from, to);
  const heatmap = useHeatmap(month);
  const curve = useEquityCurve(from, to, "day");
  const sync = useSyncStatus();
  const recent = useTrades({ status: "closed", limit: 10, intraday_only: false });

  function setMonth(next: string) {
    setSelectedDay(null);
    router.replace(next === currentMonth() ? "/" : `/?month=${next}`);
  }

  function openDay(date: string) {
    setSelectedDay(date);
    router.push(`/trades?date_from=${date}&date_to=${date}`);
  }

  const empty = summary.data?.trades === 0;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <MonthPicker month={month} onChange={setMonth} />
      </div>

      <TodayCard
        data={summary.data}
        sync={sync.data}
        isLoading={summary.isLoading}
        month={month}
      />

      {!empty && (
        <>
          <MetricStrip data={summary.data} isLoading={summary.isLoading} />
          {summary.data?.low_sample && <LowSampleNote trades={summary.data.trades} />}
        </>
      )}

      <Section title="Calendar">
        <CalendarHeatmap
          data={heatmap.data}
          isLoading={heatmap.isLoading}
          selected={selectedDay}
          onSelect={openDay}
        />
      </Section>

      <Section title="Equity curve">
        <EquityCurveChart data={curve.data} isLoading={curve.isLoading} />
      </Section>

      <Section title="Recent trades">
        {recent.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : recent.data && recent.data.items.length > 0 ? (
          <div className="overflow-hidden rounded-[6px] border border-rule bg-sheet">
            {recent.data.items.map((trade) => (
              <TradeRow
                key={trade.group_key}
                trade={trade}
                onOpen={() => router.push(`/trades?open=${encodeURIComponent(trade.group_key)}`)}
              />
            ))}
          </div>
        ) : (
          <EmptyState message="No trades yet. Sync now or import a CSV file." />
        )}
      </Section>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <HomeContent />
    </Suspense>
  );
}
