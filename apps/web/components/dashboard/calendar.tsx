"use client";

import { useMemo } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { formatMoneyCompact, moneyLabel, toIsoDate } from "@/lib/format";
import type { Heatmap, HeatmapDay } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  DESIGN.md 9 and FR-DASH-04. Seven columns, day number top-left, net P&L
  centred in the condensed figure face. Intensity is scaled to the month's
  largest absolute day; the amount is always printed, so colour is never the
  only cue. Holidays are hatched rather than tinted.
*/

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

/*
  Written out in full because Tailwind extracts class names statically: a
  template literal like `bg-profit-${step}` is never generated and the cells
  come out blank.
*/
const TINTS = {
  profit: ["bg-profit-1", "bg-profit-2", "bg-profit-3"],
  loss: ["bg-loss-1", "bg-loss-2", "bg-loss-3"],
} as const;

function tintFor(net: number, largest: number): string {
  if (net === 0 || largest === 0) return "";
  const intensity = Math.abs(net) / largest;
  const step = intensity < 0.33 ? 0 : intensity < 0.66 ? 1 : 2;
  return net > 0 ? TINTS.profit[step] : TINTS.loss[step];
}

function Cell({
  day,
  largest,
  isToday,
  selected,
  onSelect,
}: {
  day: HeatmapDay;
  largest: number;
  isToday: boolean;
  selected: boolean;
  onSelect: (date: string) => void;
}) {
  const net = Number(day.net_pnl);
  const dayNumber = Number(day.trade_date.slice(8, 10));
  const traded = day.trades_count > 0;

  return (
    <button
      type="button"
      onClick={() => onSelect(day.trade_date)}
      aria-label={`${day.trade_date}, net ${moneyLabel(day.net_pnl)}, ${day.trades_count} trades`}
      aria-pressed={selected}
      className={cn(
        "relative flex h-[52px] flex-col items-center justify-center rounded-[6px]",
        "border border-transparent px-1",
        traded && tintFor(net, largest),
        day.is_holiday && !traded && "hatched",
        // Today gets a marker ring; a selected day gets the marker fill.
        isToday && "border-2 border-marker",
        selected && "bg-marker",
      )}
    >
      <span className="absolute top-1 left-1.5 text-[11px] leading-none text-slate">
        {dayNumber}
      </span>
      {traded && (
        <span className="font-condensed text-figure tabular text-graphite">
          {formatMoneyCompact(day.net_pnl, { signed: true })}
        </span>
      )}
    </button>
  );
}

export function CalendarHeatmap({
  data,
  isLoading,
  selected,
  onSelect,
}: {
  data: Heatmap | undefined;
  isLoading: boolean;
  selected: string | null;
  onSelect: (date: string) => void;
}) {
  const today = useMemo(() => toIsoDate(new Date()), []);

  const leadingBlanks = useMemo(() => {
    if (!data?.days.length) return 0;
    // Monday-start grid, matching the weekly totals the API returns.
    const first = new Date(`${data.days[0].trade_date}T00:00:00Z`);
    return (first.getUTCDay() + 6) % 7;
  }, [data]);

  if (isLoading) return <Skeleton className="h-[340px] w-full rounded-[6px]" />;
  if (!data) return null;

  const largest = Math.abs(Number(data.max_abs_day));

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-7 gap-0.5" aria-hidden>
        {WEEKDAYS.map((label, index) => (
          <span key={index} className="py-1 text-center text-caption text-slate">
            {label}
          </span>
        ))}
      </div>

      <div role="grid" aria-label={`Daily net profit and loss for ${data.month}`}
        className="grid grid-cols-7 gap-0.5">
        {Array.from({ length: leadingBlanks }, (_, index) => (
          <span key={`blank-${index}`} aria-hidden />
        ))}
        {data.days.map((day) => (
          <Cell
            key={day.trade_date}
            day={day}
            largest={largest}
            isToday={day.trade_date === today}
            selected={day.trade_date === selected}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
