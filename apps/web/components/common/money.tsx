import { formatMoney, formatMoneyCompact, moneyLabel, sign, type Money } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
  Design spec §5:
  Numbers are heroes. P&L, win rate, equity — big, monospaced, tabular, colour-coded.
  Profit = emerald, loss = rose.
 */
export function Pnl({
  value,
  compact = false,
  glow = false,
  className,
}: {
  value: Money;
  compact?: boolean;
  glow?: boolean;
  className?: string;
}) {
  const tone = sign(value);
  const text = compact
    ? formatMoneyCompact(value, { signed: true })
    : formatMoney(value, { signed: true });

  return (
    <span
      className={cn(
        "tabular font-mono tracking-tight",
        tone === "profit" && "text-profit",
        tone === "loss" && "text-loss",
        tone === "flat" && "text-text-1",
        glow && tone === "profit" && "glow-profit",
        glow && tone === "loss" && "glow-loss",
        className,
      )}
    >
      <span aria-hidden>{text}</span>
      <span className="sr-only">{moneyLabel(value)}</span>
    </span>
  );
}

/** An amount with no sign semantics: charges, limits, turnover. */
export function Amount({ value, className }: { value: Money; className?: string }) {
  return <span className={cn("tabular font-mono text-text-0", className)}>{formatMoney(value)}</span>;
}
