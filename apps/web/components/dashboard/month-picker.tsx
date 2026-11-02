"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

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

/*
  Design spec §10.1 Section A:
  Glass pill month bar with animated chevron icon buttons.
*/
export function MonthPicker({
  month,
  onChange,
}: {
  month: string;
  onChange: (month: string) => void;
}) {
  const atLatest = month >= currentMonth();

  return (
    <div className="glass inline-flex items-center gap-2 rounded-full p-1.5 shadow-sm">
      <Button
        variant="quiet"
        size="icon-sm"
        onClick={() => onChange(shiftMonth(month, -1))}
        aria-label="Previous month"
        className="size-8 rounded-full hover:bg-glass-2"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
      </Button>

      <span
        aria-live="polite"
        className="min-w-[10rem] px-2 text-center text-body font-semibold text-text-0 select-none"
      >
        {label(month)}
      </span>

      <Button
        variant="quiet"
        size="icon-sm"
        onClick={() => onChange(shiftMonth(month, 1))}
        disabled={atLatest}
        aria-label="Next month"
        className="size-8 rounded-full hover:bg-glass-2 disabled:opacity-30"
      >
        <ChevronRight size={16} strokeWidth={2} aria-hidden />
      </Button>
    </div>
  );
}
