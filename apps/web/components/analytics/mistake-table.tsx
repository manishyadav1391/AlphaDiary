"use client";

import { formatCount, formatMoney, formatPercent } from "@/lib/format";
import type { MistakeCost } from "@/lib/types";

/*
  FR-AN-05. A table, not a chart: the useful comparison is a ranked list of
  costs with their counts and averages, and five columns of exact numbers read
  better than five bars.
*/
export function MistakeTable({ rows }: { rows: MistakeCost[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-body text-text-2">
        No mistake tags on the trades in this range. Tag a few in the journal and the cost of each
        habit appears here, worst first.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-x-auto rounded-[12px] border border-glass-border">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-glass-border text-left">
              <th className="px-3 py-2 text-label font-normal text-text-2">Mistake</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Trades</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Share</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Total</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Average</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const total = Number(row.net_pnl);
              return (
                <tr key={row.tag} className="border-b border-glass-border last:border-b-0">
                  <td className="px-3 py-2 text-body text-text-0">{row.tag}</td>
                  <td className="px-3 py-2 text-right font-mono text-mono-sm text-text-1">
                    {formatCount(row.trades)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-mono-sm text-text-1">
                    {formatPercent(row.share_of_trades)}
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-mono text-mono-sm ${
                      total >= 0 ? "text-profit" : "text-loss"
                    }`}
                  >
                    {formatMoney(row.net_pnl, { signed: true })}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-mono-sm text-text-1">
                    {formatMoney(row.avg_net_pnl, { signed: true })}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-caption text-text-2">
        Sorted by total cost. &ldquo;Share&rdquo; is the proportion of trades in this range carrying
        the tag, so the shares can add up to more than 100% when a trade has several.
      </p>
    </div>
  );
}
