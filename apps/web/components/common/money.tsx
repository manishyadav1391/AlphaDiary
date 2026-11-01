import { formatMoney, formatMoneyCompact, moneyLabel, sign, type Money } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * A P&L figure.
 *
 * Colour is never the only cue: the sign is always printed, and a screen
 * reader gets "minus 850 rupees" rather than a bare number (DESIGN.md 5, 15).
 * Coloured P&L sits on sheet or chalk only, never on a tint.
 */
export function Pnl({
  value,
  compact = false,
  className,
}: {
  value: Money;
  compact?: boolean;
  className?: string;
}) {
  const tone = sign(value);
  const text = compact
    ? formatMoneyCompact(value, { signed: true })
    : formatMoney(value, { signed: true });

  return (
    <span
      className={cn(
        "tabular",
        tone === "profit" && "text-profit",
        tone === "loss" && "text-loss",
        tone === "flat" && "text-graphite",
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
  return <span className={cn("tabular", className)}>{formatMoney(value)}</span>;
}
