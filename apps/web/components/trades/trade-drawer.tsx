"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Amount, Pnl } from "@/components/common/money";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, NumberInput, TextArea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { EMPTY, formatDate, formatDuration, formatPrice, formatR, formatTime } from "@/lib/format";
import { useSaveTrade, useTrade } from "@/lib/queries";
import type { TradeDetail } from "@/lib/types";

/*
  SCREENS.md 6, as a bottom sheet on phones and a right-hand panel from
  768 px (DESIGN.md 9). Journal first on narrow screens, because tagging the
  trade is the job; the charge breakdown sits under it.
*/

const RATINGS = [1, 2, 3, 4, 5] as const;

function ChargeRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-2 last:border-0">
      <span className="text-secondary text-slate">{label}</span>
      <Amount value={value} className="text-secondary text-graphite" />
    </div>
  );
}

/**
 * Initial values come from props, and the panel is keyed on `group_key`, so
 * opening a different trade remounts the form. Copying props into state from
 * an effect would cascade a render on every refetch.
 */
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

      <Field label="Why I took it">
        {(id) => (
          <TextArea id={id} value={entryReason} onChange={(e) => setEntryReason(e.target.value)} />
        )}
      </Field>

      <Field label="Lessons">
        {(id) => <TextArea id={id} value={lessons} onChange={(e) => setLessons(e.target.value)} />}
      </Field>

      <div className="flex flex-col gap-2">
        <span className="text-secondary text-slate">Execution</span>
        <div className="flex gap-2">
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
              className={`size-11 rounded-[6px] border text-row tabular ${
                rating === value
                  ? "border-graphite bg-graphite text-white"
                  : "border-rule bg-sheet text-graphite hover:bg-fog"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={save.isPending} size="md">
          {save.isPending ? "Saving…" : "Save"}
        </Button>
        {save.isSuccess && !save.isPending && (
          <span className="text-secondary text-slate" role="status">
            Saved
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
    <div className="fixed inset-0 z-30 flex" role="dialog" aria-modal aria-label="Trade detail">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="flex-1 bg-[rgba(26,31,38,0.4)]"
      />

      <div
        className="flex h-full w-full max-w-[560px] flex-col overflow-y-auto bg-sheet
          shadow-[0_-8px_24px_rgba(26,31,38,0.12)] md:border-l md:border-rule"
      >
        <div className="flex items-start justify-between gap-4 border-b border-rule p-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-section text-graphite">
              {trade ? trade.tradingsymbol : "Trade"}
            </h2>
            {trade && (
              <p className="text-secondary text-slate">
                {formatDate(trade.trade_date)} · {trade.product} ·{" "}
                {trade.direction === "LONG" ? "Long" : "Short"}
              </p>
            )}
          </div>
          <Button variant="quiet" size="icon" onClick={onClose} aria-label="Close">
            <X size={20} aria-hidden />
          </Button>
        </div>

        {isLoading || !trade ? (
          <div className="flex flex-col gap-4 p-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : (
          <div className="flex flex-col gap-8 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-4">
              <Pnl value={trade.net_pnl} className="text-title" />
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-secondary text-slate">
                <span className="tabular">{trade.qty_max} qty</span>
                <span className="tabular">
                  {formatPrice(trade.avg_entry)} → {formatPrice(trade.avg_exit)}
                </span>
                <span className="tabular">{formatDuration(trade.hold_seconds)}</span>
                <span className="tabular">
                  {trade.derived.r_multiple ? formatR(trade.derived.r_multiple) : EMPTY}
                </span>
              </div>
            </div>

            {trade.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {trade.tags.map((tag) => (
                  <Chip key={tag.id}>{tag.name}</Chip>
                ))}
              </div>
            )}

            <Journal key={trade.group_key} trade={trade} />

            <section className="flex flex-col gap-2">
              <h3 className="text-section text-graphite">Charges</h3>
              <ChargeRow label="Brokerage" value={trade.charges.brokerage} />
              <ChargeRow label="STT / CTT" value={trade.charges.stt_ctt} />
              <ChargeRow label="Exchange" value={trade.charges.exchange_txn} />
              <ChargeRow label="SEBI" value={trade.charges.sebi} />
              <ChargeRow label="Stamp duty" value={trade.charges.stamp} />
              <ChargeRow label="GST" value={trade.charges.gst} />
              <div className="flex items-baseline justify-between gap-4 pt-2">
                <span className="text-row text-graphite">Total</span>
                <Amount value={trade.charges.total} className="text-row text-graphite" />
              </div>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-section text-graphite">Fills</h3>
              <table className="w-full text-secondary">
                <thead>
                  <tr className="border-b border-rule text-left text-caption text-slate">
                    <th className="py-2 font-normal">Time</th>
                    <th className="py-2 font-normal">Side</th>
                    <th className="py-2 text-right font-normal">Qty</th>
                    <th className="py-2 text-right font-normal">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {trade.fills.map((fill) => (
                    <tr key={`${fill.id}-${fill.role}`} className="border-b border-rule last:border-0">
                      <td className="py-2 tabular text-graphite">{formatTime(fill.filled_at)}</td>
                      <td className="py-2 text-graphite">{fill.side}</td>
                      <td className="py-2 text-right tabular text-graphite">
                        {fill.quantity_used}
                      </td>
                      <td className="py-2 text-right tabular text-graphite">
                        {formatPrice(fill.price)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
