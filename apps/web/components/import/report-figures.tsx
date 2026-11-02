"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { formatCount, formatDate } from "@/lib/format";
import type { ImportRejection } from "@/lib/types";

/*
  Shared by the preview and the report. DESIGN.md 9: labels in caption, values
  in figure, divided by 1 px rules, no boxes.
*/

export function CountsRow({ items }: { items: { label: string; value: number }[] }) {
  return (
    <dl className="flex flex-wrap gap-x-8 gap-y-4">
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-1">
          <dt className="text-label text-text-2">{item.label}</dt>
          <dd className="text-mono-sm text-text-0">{formatCount(item.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DateRange({ from, to }: { from: string | null; to: string | null }) {
  if (!from && !to) return null;
  return (
    <p className="text-body text-text-2">
      {formatDate(from)} – {formatDate(to)}
    </p>
  );
}

/**
 * How the missing product column was resolved (FR-IMP-06).
 *
 * Console's tradebook has no product column, so MIS and CNC are inferred from
 * whether a position flattened within its own day. The two are charged very
 * differently, so the split is shown rather than silently assumed.
 */
export function ProductSplit({ products }: { products: Record<string, number> }) {
  const entries = Object.entries(products);
  if (entries.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-label text-text-2">Product split (inferred)</p>
      <div className="flex flex-wrap gap-2">
        {entries.map(([product, count]) => (
          <Chip key={product}>
            {product} {formatCount(count)}
          </Chip>
        ))}
      </div>
    </div>
  );
}

/** Rows that imported against a placeholder instrument (FR-IMP-05). */
export function UnresolvedSymbols({ symbols }: { symbols: string[] }) {
  const [expanded, setExpanded] = useState(false);
  if (symbols.length === 0) return null;

  const shown = expanded ? symbols : symbols.slice(0, 12);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-label text-text-2">Symbols not in the instrument list</p>
      <p className="text-body text-text-2">
        These rows imported with a placeholder instrument, so asset class and charges may be
        wrong until the instrument list is refreshed. Run{" "}
        <span className="rounded-[6px] bg-glass-2 px-1 font-mono">make instruments</span>, then import
        the file again.
      </p>
      <div className="flex flex-wrap gap-2">
        {shown.map((symbol) => (
          <Chip key={symbol} tone="marker">
            {symbol}
          </Chip>
        ))}
      </div>
      {!expanded && symbols.length > shown.length && (
        <Button variant="quiet" size="md" className="self-start" onClick={() => setExpanded(true)}>
          Show all {formatCount(symbols.length)}
        </Button>
      )}
    </div>
  );
}

/** Rows that did not import at all — distinct from unresolved symbols. */
export function Rejections({ rejections }: { rejections: ImportRejection[] }) {
  const [expanded, setExpanded] = useState(false);
  if (rejections.length === 0) return null;

  const shown = expanded ? rejections : rejections.slice(0, 20);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-label text-text-2">Rejected rows</p>
      <div className="overflow-hidden rounded-[6px] border border-glass-border bg-glass-1">
        {shown.map((rejection) => (
          <div
            key={`${rejection.row}-${rejection.reason}`}
            className="flex gap-3 border-b border-glass-border px-3 py-2 last:border-b-0"
          >
            <span className="w-14 shrink-0 text-right text-mono-sm text-text-2">
              {rejection.row}
            </span>
            <span className="text-body text-text-0">{rejection.reason}</span>
          </div>
        ))}
      </div>
      {!expanded && rejections.length > shown.length && (
        <Button variant="quiet" size="md" className="self-start" onClick={() => setExpanded(true)}>
          Show all {formatCount(rejections.length)}
        </Button>
      )}
    </div>
  );
}
