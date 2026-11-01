import { cn } from "@/lib/utils";

/**
 * A fog block the exact size of the content it stands in for, with a very
 * subtle pulse that stops under reduced motion (DESIGN.md 9 and 11).
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-[6px] bg-fog motion-safe:animate-pulse",
        className,
      )}
    />
  );
}
