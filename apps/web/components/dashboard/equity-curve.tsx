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
import { TrendingUp } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { formatDateShort, formatMoney, formatMoneyCompact } from "@/lib/format";
import type { EquityCurve } from "@/lib/types";

interface Point {
  label: string;
  cumulative: number;
}

function toPoints(data: EquityCurve): Point[] {
  return data.points.map((point) => ({
    label: point.label,
    cumulative: Number(point.cumulative),
  }));
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
  const isPos = point.cumulative >= 0;

  return (
    <div className="glass glass--strong rounded-[14px] border-glass-border-strong px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <p className="text-caption font-medium text-text-2">{formatDateShort(point.label)}</p>
      <p
        className={`font-mono text-body font-bold tabular ${
          isPos ? "text-profit" : "text-loss"
        }`}
      >
        {formatMoney(point.cumulative, { signed: true })}
      </p>
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
  if (isLoading) return <Skeleton className="h-[280px] w-full rounded-[20px]" />;

  if (!data || data.points.length === 0) {
    return (
      <div className="glass flex h-[280px] flex-col items-center justify-center gap-3 p-6 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-violet-600/10 border border-violet-400/20 text-violet-400">
          <TrendingUp className="size-6" />
        </div>
        <p className="text-body font-medium text-text-1">
          Your equity curve will appear after your first closed trade.
        </p>
      </div>
    );
  }

  const points = toPoints(data);
  const days = data.points.length;
  const isOverallProfit = Number(data.net_pnl) >= 0;

  return (
    <div className="glass flex flex-col gap-4 p-5">
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="curveVioletArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="lineVioletStroke" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#a78bfa" />
                <stop offset="100%" stopColor="#8b5cf6" />
              </linearGradient>
            </defs>
            <CartesianGrid
              stroke="var(--glass-border)"
              strokeDasharray="3 4"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tickFormatter={formatDateShort}
              tick={{ fill: "var(--text-2)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--glass-border)" }}
              minTickGap={28}
            />
            <YAxis
              tickFormatter={(value: number) => formatMoneyCompact(value)}
              tick={{ fill: "var(--text-2)", fontSize: 12, fontFamily: "monospace" }}
              tickLine={false}
              axisLine={false}
              width={70}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "rgba(139, 92, 246, 0.4)", strokeWidth: 1.5, strokeDasharray: "4 4" }}
            />
            <ReferenceLine y={0} stroke="var(--neutral)" strokeWidth={1} />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke="none"
              fill="url(#curveVioletArea)"
              isAnimationActive={true}
              animationDuration={1200}
            />
            <Line
              type="monotone"
              dataKey="cumulative"
              stroke="url(#lineVioletStroke)"
              strokeWidth={2.5}
              dot={false}
              activeDot={{
                r: 5,
                fill: "#8b5cf6",
                stroke: "#ffffff",
                strokeWidth: 2,
              }}
              isAnimationActive={true}
              animationDuration={1200}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between border-t border-glass-border pt-3 text-caption text-text-2">
        <span>
          Net{" "}
          <strong className={isOverallProfit ? "text-profit" : "text-loss"}>
            {formatMoney(data.net_pnl, { signed: true })}
          </strong>{" "}
          over {days} {data.by === "day" ? (days === 1 ? "trading day" : "trading days") : "trades"}
        </span>
        <span className="font-mono text-[11px] text-text-disabled">Area: Cumulative Net P&L</span>
      </div>
    </div>
  );
}
