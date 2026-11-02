"use client";

import { Chip } from "@/components/ui/chip";
import { formatCount, formatDateShort, formatPrice } from "@/lib/format";
import type { ImportPreviewRow } from "@/lib/types";

/*
  DESIGN.md 9: divided rows on phones, a real table from 768 px, numbers
  right-aligned in Condensed figures.
*/
export function PreviewTable({
  rows,
  totalRows,
}: {
  rows: ImportPreviewRow[];
  totalRows: number;
}) {
  if (rows.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {/* Phones */}
      <div className="overflow-hidden rounded-[6px] border border-glass-border bg-glass-1 md:hidden">
        {rows.map((row) => (
          <div
            key={row.trade_id}
            className="flex flex-col gap-1 border-b border-glass-border px-3 py-2 last:border-b-0"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-body text-text-0">{row.symbol}</span>
              <span className="text-body text-text-2">
                {row.side} · {formatDateShort(row.trade_date)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-mono-sm text-text-2">
                {formatCount(row.quantity)} @ {formatPrice(row.price, 4)}
              </span>
              <Chip>{row.product}</Chip>
            </div>
          </div>
        ))}
      </div>

      {/* Tablet and up */}
      <div className="hidden overflow-x-auto rounded-[6px] border border-glass-border bg-glass-1 md:block">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-glass-border text-left">
              <th className="px-3 py-2 text-label font-normal text-text-2">Date</th>
              <th className="px-3 py-2 text-label font-normal text-text-2">Symbol</th>
              <th className="px-3 py-2 text-label font-normal text-text-2">Exchange</th>
              <th className="px-3 py-2 text-label font-normal text-text-2">Side</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Qty</th>
              <th className="px-3 py-2 text-right text-label font-normal text-text-2">Price</th>
              <th className="px-3 py-2 text-label font-normal text-text-2">Product</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.trade_id} className="border-b border-glass-border last:border-b-0">
                <td className="px-3 py-2 text-body font-mono text-text-2">
                  {formatDateShort(row.trade_date)}
                </td>
                <td className="px-3 py-2 text-body text-text-0">{row.symbol}</td>
                <td className="px-3 py-2 text-body text-text-2">{row.exchange}</td>
                <td className="px-3 py-2 text-body text-text-2">{row.side}</td>
                <td className="px-3 py-2 text-right text-mono-sm text-text-0">
                  {formatCount(row.quantity)}
                </td>
                <td className="px-3 py-2 text-right text-mono-sm text-text-0">
                  {formatPrice(row.price, 4)}
                </td>
                <td className="px-3 py-2 text-body text-text-2">{row.product}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-label text-text-2">
        First {formatCount(rows.length)} rows of {formatCount(totalRows)}.
      </p>
    </div>
  );
}
