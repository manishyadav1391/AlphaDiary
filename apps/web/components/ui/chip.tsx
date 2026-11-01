import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/*
  DESIGN.md 9: radius 6, 28 px high, fog background, graphite text. Selected
  inverts to graphite. "Needs review" is one of the few places the marker is
  allowed (principle 3).
*/
export function Chip({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: "default" | "selected" | "marker" | "profit" | "loss";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center rounded-[6px] px-2.5 text-secondary",
        tone === "default" && "bg-fog text-graphite",
        tone === "selected" && "bg-graphite text-white",
        tone === "marker" && "bg-marker text-graphite",
        tone === "profit" && "bg-profit-1 text-graphite",
        tone === "loss" && "bg-loss-1 text-graphite",
        className,
      )}
    >
      {children}
    </span>
  );
}
