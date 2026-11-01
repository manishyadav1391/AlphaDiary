"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

/*
  FR-DASH-01: a range selector defaulting to this month, held in the URL so a
  view can be bookmarked and shared. Stepping back a month is the only way to
  reach a past month's trades, so it is navigation rather than decoration.
*/

export function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/** The first and last day of a `YYYY-MM`, clamped to today in the live month. */
export function monthRange(month: string): { from: string; to: string } {
  const [year, index] = month.split("-").map(Number);
  const first = `${month}-01`;
  const lastDay = new Date(year, index, 0).getDate();
  const last = `${month}-${String(lastDay).padStart(2, "0")}`;
  return { from: first, to: last };
}

export function shiftMonth(month: string, step: number): string {
  const [year, index] = month.split("-").map(Number);
  const moved = new Date(year, index - 1 + step, 1);
  return `${moved.getFullYear()}-${String(moved.getMonth() + 1).padStart(2, "0")}`;
}

function label(month: string): string {
  const [year, index] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(
    new Date(year, index - 1, 1),
  );
}

export function MonthPicker({
  month,
  onChange,
}: {
  month: string;
  onChange: (month: string) => void;
}) {
  const atLatest = month >= currentMonth();

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="quiet"
        size="icon"
        onClick={() => onChange(shiftMonth(month, -1))}
        aria-label="Previous month"
      >
        <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
      </Button>

      <span aria-live="polite" className="min-w-[9.5rem] text-center text-row text-graphite">
        {label(month)}
      </span>

      <Button
        variant="quiet"
        size="icon"
        onClick={() => onChange(shiftMonth(month, 1))}
        disabled={atLatest}
        aria-label="Next month"
      >
        <ChevronRight size={20} strokeWidth={1.75} aria-hidden />
      </Button>
    </div>
  );
}
