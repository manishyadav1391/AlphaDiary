import { cn } from "@/lib/utils";

/**
  Design spec §9.9:
  Glass blocks with shimmering violet-tinted gradient sweep (1.4s loop).
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-[12px] border border-glass-border/40 skeleton-shimmer",
        className,
      )}
    />
  );
}
