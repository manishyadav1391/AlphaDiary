"use client";

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCount, formatDate, formatMoney, formatPercent } from "@/lib/format";
import type { RiskReport } from "@/lib/types";

/*
  FR-AN-04. The headline risk numbers are stat tiles, not charts: each is a
  single value, and a chart of one number is an anti-pattern.

  The R-multiple histogram is a bar chart whose colour encodes polarity —
  bins below 0R are losses, bins above are wins — with no legend, because it
  is one series and the axis already names the bins.
*/

function Tile({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "profit" | "loss";
  hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-[12px] border border-glass-border bg-glass-1 p-3">
      <span className="text-label text-text-2">{label}</span>
      <span
        className={`font-mono text-mono-lg font-bold ${
          tone === "profit" ? "text-profit" : tone === "loss" ? "text-loss" : "text-text-0"
        }`}
      >
        {value}
      </span>
      {hint && <span className="text-caption text-text-2">{hint}</span>}
    </div>
  );
}

function HistogramTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { label: string; trades: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const bin = payload[0].payload;
  return (
    <div className="glass glass--strong rounded-[14px] border-glass-border-strong px-4 py-2.5 shadow-2xl backdrop-blur-xl">
      <p className="text-caption font-medium text-text-2">{bin.label}</p>
      <p className="font-mono text-body font-bold text-text-0">
        {formatCount(bin.trades)} trades
      </p>
    </div>
  );
}

export function RiskPanel({ risk }: { risk: RiskReport }) {
  const stopShare =
    risk.trades_total > 0 ? risk.trades_with_stop / risk.trades_total : null;

  const drawdownWindow =
    risk.drawdown_from && risk.drawdown_to
      ? `${formatDate(risk.drawdown_from)} → ${formatDate(risk.drawdown_to)}`
      : undefined;

  const binned = risk.r_histogram.filter((bin) => bin.trades > 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        <Tile
          label="Max drawdown"
          value={formatMoney(risk.max_drawdown)}
          tone="loss"
          hint={drawdownWindow}
        />
        <Tile
          label="Largest win"
          value={risk.largest_win ? formatMoney(risk.largest_win, { signed: true }) : "–"}
          tone="profit"
        />
        <Tile
          label="Largest loss"
          value={risk.largest_loss ? formatMoney(risk.largest_loss, { signed: true }) : "–"}
          tone="loss"
        />
        <Tile label="Longest losing streak" value={formatCount(risk.longest_losing_streak)} />
        <Tile label="Longest winning streak" value={formatCount(risk.longest_winning_streak)} />
        <Tile
          label="Traded with a stop"
          value={stopShare === null ? "–" : formatPercent(stopShare)}
          hint={`${formatCount(risk.trades_with_stop)} of ${formatCount(risk.trades_total)} trades`}
        />
        <Tile
          label="Average planned risk"
          value={risk.avg_planned_risk ? formatMoney(risk.avg_planned_risk) : "–"}
          hint={risk.avg_planned_risk ? undefined : "No stop-losses recorded"}
        />
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-h3 text-text-0">R-multiple distribution</h3>
        {binned.length === 0 ? (
          <p className="text-body text-text-2">
            No trade has both a planned entry and a stop-loss, so there is no risk to measure R
            against. Record a stop in the journal and these appear.
          </p>
        ) : (
          <>
            <div className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={risk.r_histogram} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
                  <CartesianGrid
                    stroke="var(--glass-border)"
                    strokeDasharray="3 4"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "var(--text-2)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={{ stroke: "var(--glass-border)" }}
                    interval={0}
                  />
                  <YAxis
                    tick={{ fill: "var(--text-2)", fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                    allowDecimals={false}
                  />
                  <Tooltip content={<HistogramTooltip />} cursor={{ fill: "var(--glass-2)" }} />
                  <Bar dataKey="trades" radius={[4, 4, 0, 0]} maxBarSize={48}>
                    {risk.r_histogram.map((bin) => (
                      <Cell
                        key={bin.label}
                        fill={bin.label.includes("-") ? "var(--loss)" : "var(--profit)"}
                        stroke="var(--bg-0)"
                        strokeWidth={2}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-caption text-text-2">
              Each bar counts trades whose result fell in that multiple of the risk planned at
              entry. Trades without a stop-loss are excluded rather than counted as zero.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
