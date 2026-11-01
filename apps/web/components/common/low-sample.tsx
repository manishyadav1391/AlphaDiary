/**
 * Under 20 trades the numbers are not worth much and the interface says so
 * plainly rather than implying confidence (DESIGN.md 10).
 */
export function LowSampleNote({ trades }: { trades: number }) {
  return (
    <p className="text-secondary text-slate">
      Based on {trades} {trades === 1 ? "trade" : "trades"}. Treat with caution.
    </p>
  );
}
