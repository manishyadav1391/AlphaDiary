"use client";

import { useMemo } from "react";
import { Star } from "lucide-react";
import { motion } from "motion/react";

import { Skeleton } from "@/components/ui/skeleton";
import { formatMoneyCompact, moneyLabel, toIsoDate } from "@/lib/format";
import type { Heatmap, HeatmapDay } from "@/lib/types";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function Cell({
  day,
  largest,
  isToday,
  isBestDay,
  isWeekend,
  selected,
  onSelect,
  row,
  col,
}: {
  day: HeatmapDay;
  largest: number;
  isToday: boolean;
  isBestDay: boolean;
  isWeekend: boolean;
  selected: boolean;
  onSelect: (date: string) => void;
  index?: number;
  row: number;
  col: number;
}) {
  const net = Number(day.net_pnl);
  const dayNumber = Number(day.trade_date.slice(8, 10));
  const traded = day.trades_count > 0;
  const isProfit = net > 0;
  const isLoss = net < 0;

  // Heatmap intensity calculation (spec §10.1 C: 0.08 -> 0.38 alpha)
  const intensity = largest > 0 ? Math.min(Math.abs(net) / largest, 1) : 0;
  const alpha = 0.08 + intensity * 0.3;

  const bgStyle = traded
    ? isProfit
      ? { backgroundColor: `rgba(52, 211, 153, ${alpha.toFixed(2)})` }
      : isLoss
        ? { backgroundColor: `rgba(251, 113, 133, ${alpha.toFixed(2)})` }
        : undefined
    : undefined;

  // Diagonal stagger delay: (row + col) * 18ms
  const delay = (row + col) * 0.018;

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: isWeekend ? 0.6 : 1, scale: 1 }}
      transition={{ duration: 0.35, delay }}
      onClick={() => onSelect(day.trade_date)}
      aria-label={`${day.trade_date}, net ${moneyLabel(day.net_pnl)}, ${day.trades_count} trades`}
      aria-pressed={selected}
      style={bgStyle}
      className={cn(
        "glass relative flex min-h-[76px] md:min-h-[86px] flex-col justify-between rounded-[12px] p-2.5 text-left transition-all duration-200 select-none",
        !traded && "bg-glass-1 hover:bg-glass-2",
        !isWeekend && "hover:-translate-y-0.5 hover:shadow-lg",
        day.is_holiday && !traded && "hatched opacity-40",
        isToday && "ring-breathe z-10",
        selected && "border-violet-400 bg-violet-600/20 shadow-[0_0_20px_rgba(139,92,246,0.4)]",
      )}
    >
      {/* Top row: day number + trade count / best day star */}
      <div className="flex items-center justify-between w-full">
        <span
          className={cn(
            "text-label font-semibold",
            isToday ? "text-violet-300 font-bold" : "text-text-2",
          )}
        >
          {dayNumber}
        </span>

        <div className="flex items-center gap-1">
          {isBestDay && traded && (
            <Star size={12} className="fill-amber-400 text-amber-400" aria-label="Best day of the month" />
          )}
          {traded && (
            <span className="flex size-4 items-center justify-center rounded-full bg-glass-3 text-[10px] font-mono text-text-1">
              {day.trades_count}
            </span>
          )}
        </div>
      </div>

      {/* Bottom row: P&L figure */}
      <div className="mt-2 w-full text-center md:text-left">
        {traded ? (
          <span
            className={cn(
              "font-mono text-mono-sm font-semibold tracking-tight tabular block truncate",
              isProfit && "text-profit glow-profit",
              isLoss && "text-loss glow-loss",
            )}
          >
            {formatMoneyCompact(day.net_pnl, { signed: true })}
          </span>
        ) : day.is_holiday ? (
          <span className="text-[10px] text-text-disabled">No session</span>
        ) : null}
      </div>
    </motion.button>
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
    // Monday-start grid
    const first = new Date(`${data.days[0].trade_date}T00:00:00Z`);
    return (first.getUTCDay() + 6) % 7;
  }, [data]);

  const { largest, bestDate } = useMemo(() => {
    if (!data?.days.length) return { largest: 0, bestDate: null };
    const maxAbs = Math.abs(Number(data.max_abs_day));
    let bestVal = -Infinity;
    let best: string | null = null;
    for (const d of data.days) {
      const val = Number(d.net_pnl);
      if (val > bestVal && d.trades_count > 0) {
        bestVal = val;
        best = d.trade_date;
      }
    }
    return { largest: maxAbs, bestDate: bestVal > 0 ? best : null };
  }, [data]);

  if (isLoading) {
    return <Skeleton className="h-[420px] w-full rounded-[20px]" />;
  }

  if (!data) return null;

  return (
    <div className="glass flex flex-col gap-3 p-5">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-2" aria-hidden>
        {WEEKDAYS.map((label, index) => (
          <span
            key={index}
            className="py-1 text-center text-label uppercase tracking-wider text-text-2 font-medium"
          >
            {label}
          </span>
        ))}
      </div>

      {/* Calendar Grid */}
      <div
        role="grid"
        aria-label={`Daily net profit and loss heatmap for ${data.month}`}
        className="grid grid-cols-7 gap-2"
      >
        {Array.from({ length: leadingBlanks }, (_, index) => (
          <span key={`blank-${index}`} className="opacity-0 pointer-events-none" aria-hidden />
        ))}
        {data.days.map((day, index) => {
          const totalIdx = leadingBlanks + index;
          const row = Math.floor(totalIdx / 7);
          const col = totalIdx % 7;
          const isWeekend = col >= 5;

          return (
            <Cell
              key={day.trade_date}
              day={day}
              largest={largest}
              isToday={day.trade_date === today}
              isBestDay={day.trade_date === bestDate}
              isWeekend={isWeekend}
              selected={day.trade_date === selected}
              onSelect={onSelect}
              index={index}
              row={row}
              col={col}
            />
          );
        })}
      </div>
    </div>
  );
}
