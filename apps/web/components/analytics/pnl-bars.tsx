"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { formatCount, formatMoney, formatMoneyCompact, formatPercent } from "@/lib/format";
import type { AnalyticsBucket } from "@/lib/types";

/*
  Net P&L per bucket.

  Colour here encodes POLARITY, not identity: profit and loss are the two poles
  of a diverging scale with zero as the neutral midpoint, which is why this is
  one series of profit/loss-tinted bars rather than a categorical palette. A
  single series needs no legend — the title names it.

  Both colours are CSS custom properties, so light and dark are separate
  selected steps rather than an automatic flip.

  DESIGN.md also requires a text summary and a table view under every chart.
*/

interface Row {
  label: string;
  net: number;
  trades: number;
  winRate: string | null;
  lowSample: boolean;
}

function toRows(buckets: AnalyticsBucket[]): Row[] {
  return buckets.map((bucket) => ({
    label: bucket.label,
    net: Number(bucket.kpis.net_pnl),
    trades: bucket.kpis.trades,
    winRate: bucket.kpis.win_rate,
    lowSample: bucket.kpis.low_sample,
  }));
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: Row }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;

  return (
    <div className="glass glass--strong rounded-[14px] border-glass-border-strong px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <p className="text-caption font-medium text-text-2">{row.label}</p>
      <p
        className={`font-mono text-body font-bold ${row.net >= 0 ? "text-profit" : "text-loss"}`}
      >
        {formatMoney(row.net, { signed: true })}
      </p>
      <p className="text-caption text-text-2">
        {formatCount(row.trades)} trades
        {row.winRate !== null && ` · ${formatPercent(row.winRate)} win rate`}
        {row.lowSample && " · low sample"}
      </p>
    </div>
  );
}

export function PnlBars({
  buckets,
  /** Rotate long category labels rather than letting them collide. */
  angledLabels = false,
}: {
  buckets: AnalyticsBucket[];
  angledLabels?: boolean;
}) {
  const [asTable, setAsTable] = useState(false);
  const rows = toRows(buckets);

  if (rows.length === 0) {
    return <p className="text-body text-text-2">No trades in this range.</p>;
  }

  const best = rows.reduce((a, b) => (b.net > a.net ? b : a));
  const worst = rows.reduce((a, b) => (b.net < a.net ? b : a));

  return (
    <div className="flex flex-col gap-3">
      {!asTable && (
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              margin={{ top: 8, right: 8, bottom: angledLabels ? 48 : 8, left: 0 }}
            >
              <CartesianGrid
                stroke="var(--glass-border)"
                strokeDasharray="3 4"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fill: "var(--text-2)", fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: "var(--glass-border)" }}
                angle={angledLabels ? -40 : 0}
                textAnchor={angledLabels ? "end" : "middle"}
                interval={0}
                height={angledLabels ? 60 : 30}
              />
              <YAxis
                tick={{ fill: "var(--text-2)", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(value: number) => formatMoneyCompact(value)}
              />
              {/* Zero is the neutral midpoint of the diverging scale. */}
              <ReferenceLine y={0} stroke="var(--neutral)" strokeWidth={1} />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ fill: "var(--glass-2)" }}
              />
              <Bar dataKey="net" radius={[4, 4, 0, 0]} maxBarSize={44}>
                {rows.map((row) => (
                  <Cell
                    key={row.label}
                    fill={row.net >= 0 ? "var(--profit)" : "var(--loss)"}
                    // A 2px surface ring keeps adjacent bars from touching.
                    stroke="var(--bg-0)"
                    strokeWidth={2}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {asTable && (
        <div className="overflow-x-auto rounded-[12px] border border-glass-border">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-glass-border text-left">
                <th className="px-3 py-2 text-label font-normal text-text-2">Bucket</th>
                <th className="px-3 py-2 text-right text-label font-normal text-text-2">Net P&amp;L</th>
                <th className="px-3 py-2 text-right text-label font-normal text-text-2">Trades</th>
                <th className="px-3 py-2 text-right text-label font-normal text-text-2">Win rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b border-glass-border last:border-b-0">
                  <td className="px-3 py-2 text-body text-text-0">{row.label}</td>
                  <td
                    className={`px-3 py-2 text-right font-mono text-mono-sm ${
                      row.net >= 0 ? "text-profit" : "text-loss"
                    }`}
                  >
                    {formatMoney(row.net, { signed: true })}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-mono-sm text-text-1">
                    {formatCount(row.trades)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-mono-sm text-text-1">
                    {row.winRate === null ? "–" : formatPercent(row.winRate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-caption text-text-2">
          Best: {best.label} at {formatMoney(best.net, { signed: true })}. Worst: {worst.label} at{" "}
          {formatMoney(worst.net, { signed: true })}.
        </p>
        <Button variant="quiet" size="sm" onClick={() => setAsTable((value) => !value)}>
          {asTable ? "View as chart" : "View as table"}
        </Button>
      </div>
    </div>
  );
}
