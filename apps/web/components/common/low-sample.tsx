import { AlertCircle } from "lucide-react";

/**
  Design spec §10:
  Low sample note under charts and metrics.
 */
export function LowSampleNote({ trades }: { trades: number }) {
  return (
    <div className="flex items-center gap-2 rounded-[10px] bg-glass-1 border border-glass-border px-3.5 py-2 text-label text-text-2">
      <AlertCircle className="size-4 text-violet-400 shrink-0" />
      <span>
        Based on {trades} {trades === 1 ? "trade" : "trades"}. Treat metrics with caution.
      </span>
    </div>
  );
}
