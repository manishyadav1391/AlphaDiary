"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Amount, Pnl } from "@/components/common/money";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, NumberInput, TextArea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDuration, formatPrice, formatR, formatTime } from "@/lib/format";
import { useSaveTrade, useTrade } from "@/lib/queries";
import type { TradeDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

const RATINGS = [1, 2, 3, 4, 5] as const;

function ChargeRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-glass-border/40 py-2.5 last:border-0">
      <span className="text-caption text-text-2">{label}</span>
      <Amount value={value} className="font-mono text-caption text-text-0" />
    </div>
  );
}

function Journal({ trade }: { trade: TradeDetail }) {
  const save = useSaveTrade(trade.group_key);
  const [lessons, setLessons] = useState(trade.journal.lessons ?? "");
  const [entryReason, setEntryReason] = useState(trade.journal.entry_reason ?? "");
  const [plannedEntry, setPlannedEntry] = useState(trade.journal.planned_entry ?? "");
  const [plannedSl, setPlannedSl] = useState(trade.journal.planned_sl ?? "");
  const [plannedTarget, setPlannedTarget] = useState(trade.journal.planned_target ?? "");
  const [rating, setRating] = useState(trade.journal.execution_rating);

  function onSave() {
    save.mutate({
      lessons: lessons || null,
      entry_reason: entryReason || null,
      planned_entry: plannedEntry || null,
      planned_sl: plannedSl || null,
      planned_target: plannedTarget || null,
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <h3 className="text-h3 font-bold text-text-0 border-b border-glass-border/60 pb-2">
        Journal & Notes
      </h3>

      <div className="grid grid-cols-3 gap-3">
        <Field label="Planned entry">
          {(id) => (
            <NumberInput id={id} value={plannedEntry} onChange={(e) => setPlannedEntry(e.target.value)} />
          )}
        </Field>
        <Field label="Stop loss">
          {(id) => (
            <NumberInput id={id} value={plannedSl} onChange={(e) => setPlannedSl(e.target.value)} />
          )}
        </Field>
        <Field label="Target">
          {(id) => (
            <NumberInput id={id} value={plannedTarget} onChange={(e) => setPlannedTarget(e.target.value)} />
          )}
        </Field>
      </div>

      <Field label="Why I took it (Entry reason)">
        {(id) => (
          <TextArea id={id} value={entryReason} onChange={(e) => setEntryReason(e.target.value)} />
        )}
      </Field>

      <Field label="Lessons learned">
        {(id) => <TextArea id={id} value={lessons} onChange={(e) => setLessons(e.target.value)} />}
      </Field>

      <div className="flex flex-col gap-2">
        <span className="text-label uppercase tracking-wider text-text-2 font-medium">
          Execution Rating
        </span>
        <div className="flex gap-2.5">
          {RATINGS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setRating(value);
                save.mutate({ execution_rating: value });
              }}
              aria-label={`Rate execution ${value} of 5`}
              aria-pressed={rating === value}
              className={cn(
                "glass flex size-11 items-center justify-center rounded-[10px] font-mono text-body font-bold transition-all select-none",
                rating === value
                  ? "border-violet-500 bg-violet-600/30 text-white shadow-[0_0_12px_rgba(139,92,246,0.4)]"
                  : "bg-glass-1 text-text-2 hover:bg-glass-2 hover:text-text-0",
              )}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Button variant="primary" onClick={onSave} loading={save.isPending} size="md">
          {save.isPending ? "Saving…" : "Save journal"}
        </Button>
        {save.isSuccess && !save.isPending && (
          <span className="text-caption font-semibold text-profit" role="status">
            Saved ✓
          </span>
        )}
      </div>
    </div>
  );
}

export function TradeDrawer({
  idOrKey,
  onClose,
}: {
  idOrKey: string | null;
  onClose: () => void;
}) {
  const { data: trade, isLoading } = useTrade(idOrKey);

  if (!idOrKey) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="Trade detail drawer"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close drawer"
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      />

      {/* Drawer surface */}
      <div
        className={cn(
          "relative z-50 flex h-full w-full max-w-[580px] flex-col overflow-y-auto",
          "glass glass--strong border-l border-glass-border-strong bg-bg-1/95 p-6 shadow-2xl backdrop-blur-2xl",
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-glass-border/60 pb-5">
          <div className="flex flex-col gap-1">
            <h2 className="text-h2 font-bold text-text-0">
              {trade ? trade.tradingsymbol : "Trade details"}
            </h2>
            {trade && (
              <p className="text-caption text-text-2">
                {formatDate(trade.trade_date)} · {trade.product} ·{" "}
                <span className={trade.direction === "LONG" ? "text-profit font-semibold" : "text-loss font-semibold"}>
                  {trade.direction === "LONG" ? "Long" : "Short"}
                </span>
              </p>
            )}
          </div>
          <Button
            variant="quiet"
            size="icon-sm"
            onClick={onClose}
            aria-label="Close"
            className="size-9 rounded-full hover:bg-glass-2"
          >
            <X size={18} aria-hidden />
          </Button>
        </div>

        {isLoading || !trade ? (
          <div className="flex flex-col gap-6 py-6">
            <Skeleton className="h-28 w-full rounded-[16px]" />
            <Skeleton className="h-64 w-full rounded-[16px]" />
          </div>
        ) : (
          <div className="flex flex-col gap-8 py-6">
            {/* P&L hero banner */}
            <div className="glass flex flex-wrap items-center justify-between gap-4 p-5 rounded-[16px]">
              <div className="flex flex-col">
                <span className="text-[11px] uppercase tracking-wider text-text-2 font-medium">
                  Net P&L
                </span>
                <Pnl value={trade.net_pnl} glow={true} className="font-mono text-h1 font-bold" />
              </div>

              <div className="flex flex-col gap-1 text-right text-caption text-text-2">
                <span className="font-mono tabular">{trade.qty_max} qty</span>
                <span className="font-mono tabular">
                  {formatPrice(trade.avg_entry)} → {formatPrice(trade.avg_exit)}
                </span>
                <span className="font-mono tabular">
                  Hold: {formatDuration(trade.hold_seconds)}
                </span>
                {trade.derived?.r_multiple && (
                  <span className="font-mono tabular font-semibold text-violet-300">
                    {formatR(trade.derived.r_multiple)}
                  </span>
                )}
              </div>
            </div>

            {/* Tags */}
            {trade.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {trade.tags.map((tag) => (
                  <Chip key={tag.id}>#{tag.name}</Chip>
                ))}
              </div>
            )}

            {/* Journal editor */}
            <Journal key={trade.group_key} trade={trade} />

            {/* Charges Breakdown */}
            <section className="glass flex flex-col gap-2 p-5 rounded-[16px]">
              <h3 className="text-h3 font-bold text-text-0 mb-1">Charges Breakdown</h3>
              <ChargeRow label="Brokerage" value={trade.charges.brokerage} />
              <ChargeRow label="STT / CTT" value={trade.charges.stt_ctt} />
              <ChargeRow label="Exchange turnover" value={trade.charges.exchange_txn} />
              <ChargeRow label="SEBI turnover" value={trade.charges.sebi} />
              <ChargeRow label="Stamp duty" value={trade.charges.stamp} />
              <ChargeRow label="GST" value={trade.charges.gst} />
              <div className="flex items-baseline justify-between gap-4 pt-3 border-t border-glass-border">
                <span className="text-body font-semibold text-text-0">Total charges</span>
                <Amount value={trade.charges.total} className="font-mono text-body font-bold" />
              </div>
            </section>

            {/* Fills Table */}
            <section className="glass flex flex-col gap-3 p-5 rounded-[16px]">
              <h3 className="text-h3 font-bold text-text-0">Fills Execution</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-caption">
                  <thead>
                    <tr className="border-b border-glass-border text-left text-text-2">
                      <th className="pb-2 font-medium">Time</th>
                      <th className="pb-2 font-medium">Side</th>
                      <th className="pb-2 text-right font-medium">Qty</th>
                      <th className="pb-2 text-right font-medium">Price</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-glass-border/30">
                    {trade.fills.map((fill) => (
                      <tr key={`${fill.id}-${fill.role}`}>
                        <td className="py-2.5 font-mono text-text-1">
                          {formatTime(fill.filled_at)}
                        </td>
                        <td className="py-2.5">
                          <span
                            className={
                              fill.side === "BUY"
                                ? "font-semibold text-profit"
                                : "font-semibold text-loss"
                            }
                          >
                            {fill.side}
                          </span>
                        </td>
                        <td className="py-2.5 text-right font-mono tabular text-text-0">
                          {fill.quantity_used}
                        </td>
                        <td className="py-2.5 text-right font-mono tabular text-text-0">
                          {formatPrice(fill.price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
