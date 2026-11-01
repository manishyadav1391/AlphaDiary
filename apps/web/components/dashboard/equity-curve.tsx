"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Skeleton } from "@/components/ui/skeleton";
import { formatDateShort, formatMoney, formatMoneyCompact } from "@/lib/format";
import type { EquityCurve } from "@/lib/types";

/*
  DESIGN.md 10. One 2 px graphite line, a dashed rule at zero, no area
  gradient. The area between the line and zero is filled with the lightest
  profit and loss tints. No default Recharts colours anywhere, and a text
  summary sits under the chart because a picture alone is not accessible.
*/

interface Point {
  label: string;
  cumulative: number;
  above: number | null;
  below: number | null;
}

function toPoints(data: EquityCurve): Point[] {
  return data.points.map((point) => {
    const value = Number(point.cumulative);
    return {
      label: point.label,
      cumulative: value,
      above: value >= 0 ? value : null,
      below: value < 0 ? value : null,
    };
  });
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: Point }>;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-[6px] border border-rule bg-sheet px-3 py-2 shadow-sm">
      <p className="text-caption text-slate">{formatDateShort(point.label)}</p>
      <p className="text-row tabular text-graphite">{formatMoney(point.cumulative)}</p>
    </div>
  );
}

export function EquityCurveChart({
  data,
  isLoading,
}: {
  data: EquityCurve | undefined;
  isLoading: boolean;
}) {
  if (isLoading) return <Skeleton className="h-[200px] w-full md:h-[280px]" />;
  if (!data || data.points.length === 0) {
    return <p className="py-8 text-center text-secondary text-slate">No closed trades yet.</p>;
  }

  const points = toPoints(data);
  const days = data.points.length;

  return (
    <figure className="flex flex-col gap-3">
      <div className="h-[200px] w-full md:h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--rule)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="label"
              tickFormatter={formatDateShort}
              tick={{ fill: "var(--slate)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--rule)" }}
              minTickGap={24}
            />
            <YAxis
              tickFormatter={(value: number) => formatMoneyCompact(value)}
              tick={{ fill: "var(--slate)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--rule)" }} />
            <Area
              dataKey="above"
              stroke="none"
              fill="var(--profit-1)"
              isAnimationActive={false}
              connectNulls
            />
            <Area
              dataKey="below"
              stroke="none"
              fill="var(--loss-1)"
              isAnimationActive={false}
              connectNulls
            />
            <ReferenceLine y={0} stroke="var(--rule)" strokeDasharray="4 4" />
            <Line
              dataKey="cumulative"
              stroke="var(--graphite)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Every chart carries a text summary (DESIGN.md 10). */}
      <figcaption className="text-secondary text-slate">
        Net {formatMoney(data.net_pnl, { signed: true })} over {days}{" "}
        {data.by === "day" ? (days === 1 ? "trading day" : "trading days") : "trades"}.
      </figcaption>
    </figure>
  );
}
