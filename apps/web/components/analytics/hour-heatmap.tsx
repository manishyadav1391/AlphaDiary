"use client";

import { formatCount, formatMoney } from "@/lib/format";
import type { HeatCell } from "@/lib/types";

/*
  FR-AN-02. Net P&L by entry hour (IST) and weekday.

  A hand-built grid rather than a charting library: the data is a sparse
  weekday × hour matrix, and a plain table of cells is both lighter and more
  accessible than coercing recharts into a heatmap.

  Colour encodes POLARITY — profit and loss diverging from a neutral zero — so
  intensity comes from one profit hue and one loss hue with a neutral empty
  cell, never a rainbow.
*/

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];

/** NSE cash hours, plus an hour either side for pre-open and late exits. */
const HOURS = [9, 10, 11, 12, 13, 14, 15];

function cellStyle(net: number, peak: number): { background: string } {
  if (net === 0 || peak === 0) return { background: "var(--glass-1)" };
  // Floor the alpha so a small-but-real value is still visible.
  const intensity = Math.min(Math.abs(net) / peak, 1) * 0.8 + 0.12;
  const hue = net > 0 ? "var(--profit)" : "var(--loss)";
  return { background: `color-mix(in oklab, ${hue} ${Math.round(intensity * 100)}%, transparent)` };
}

export function HourHeatmap({ cells }: { cells: HeatCell[] }) {
  if (cells.length === 0) {
    return <p className="text-body text-text-2">No trades in this range.</p>;
  }

  const byKey = new Map(cells.map((cell) => [`${cell.weekday}:${cell.hour}`, cell]));
  const peak = Math.max(...cells.map((cell) => Math.abs(Number(cell.net_pnl))));

  const bestCell = cells.reduce((a, b) => (Number(b.net_pnl) > Number(a.net_pnl) ? b : a));

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-[2px]">
          <caption className="sr-only">
            Net profit and loss by entry hour and weekday, in IST
          </caption>
          <thead>
            <tr>
              <th className="px-2 text-label font-normal text-text-2" />
              {HOURS.map((hour) => (
                <th
                  key={hour}
                  scope="col"
                  className="px-1 pb-1 text-center text-label font-normal text-text-2"
                >
                  {String(hour).padStart(2, "0")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WEEKDAYS.map((weekday) => (
              <tr key={weekday}>
                <th
                  scope="row"
                  className="pr-2 text-right text-label font-normal text-text-2"
                >
                  {weekday}
                </th>
                {HOURS.map((hour) => {
                  const cell = byKey.get(`${weekday}:${hour}`);
                  const net = cell ? Number(cell.net_pnl) : 0;
                  return (
                    <td
                      key={hour}
                      className="h-10 w-12 rounded-[6px] border border-glass-border text-center align-middle"
                      style={cellStyle(net, peak)}
                      // Identity is never colour-alone: the value is in the
                      // title and the trade count is printed in the cell.
                      title={
                        cell
                          ? `${weekday} ${String(hour).padStart(2, "0")}:00 — ${formatMoney(net, {
                              signed: true,
                            })} over ${formatCount(cell.trades)} trades`
                          : `${weekday} ${String(hour).padStart(2, "0")}:00 — no trades`
                      }
                    >
                      <span className="font-mono text-caption text-text-1">
                        {cell ? formatCount(cell.trades) : ""}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-caption text-text-2">
        Numbers are trade counts; the tint is net P&amp;L, green for profit and red for loss. Best
        slot: {bestCell.weekday} {String(bestCell.hour).padStart(2, "0")}:00 at{" "}
        {formatMoney(bestCell.net_pnl, { signed: true })}.
      </p>
    </div>
  );
}
