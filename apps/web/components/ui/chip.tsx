import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/*
  Design spec §9.2 & §9.6:
  Chip & status pill with glass styling, rounded pill geometry,
  soft glow, and semantic states.
*/
export type ChipTone =
  | "default"
  | "selected"
  | "marker"
  | "profit"
  | "loss"
  | "warn"
  | "bullish"
  | "bearish"
  | "neutral"
  | "calm"
  | "anxious"
  | "frustrated"
  | "greedy";

export function Chip({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: ChipTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-label font-medium transition-all duration-200 select-none",
        tone === "default" &&
          "bg-glass-1 border border-glass-border text-text-1 hover:bg-glass-2 hover:text-text-0",
        tone === "selected" &&
          "bg-violet-600/30 border border-violet-400/50 text-text-0 shadow-[0_0_16px_rgba(139,92,246,0.35)]",
        (tone === "profit" || tone === "bullish" || tone === "calm") &&
          "bg-profit-bg border border-profit/40 text-profit shadow-[0_0_16px_rgba(52,211,153,0.25)]",
        (tone === "loss" || tone === "bearish" || tone === "frustrated") &&
          "bg-loss-bg border border-loss/40 text-loss shadow-[0_0_16px_rgba(251,113,133,0.25)]",
        (tone === "warn" || tone === "anxious") &&
          "bg-warn-bg border border-warn/40 text-warn shadow-[0_0_16px_rgba(251,191,36,0.25)]",
        tone === "neutral" &&
          "bg-glass-2 border border-violet-400/30 text-text-0",
        tone === "greedy" &&
          "bg-fuchsia-500/20 border border-fuchsia-400/40 text-fuchsia-300 shadow-[0_0_16px_rgba(192,38,211,0.25)]",
        tone === "marker" &&
          "bg-warn-bg border border-warn/50 text-warn shadow-[0_0_12px_rgba(251,191,36,0.2)]",
        className,
      )}
    >
      {children}
    </span>
  );
}
