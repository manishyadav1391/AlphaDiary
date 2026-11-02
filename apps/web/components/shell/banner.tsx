import type { ReactNode } from "react";
import { AlertCircle, Info } from "lucide-react";

import { cn } from "@/lib/utils";

/*
  Design spec §14:
  Glass banner under header for auth required, notifications, or errors.
*/
export function Banner({
  message,
  tone = "notice",
  actions,
  className,
}: {
  message: string;
  tone?: "notice" | "error";
  actions?: ReactNode;
  className?: string;
}) {
  const isError = tone === "error";

  return (
    <div
      className={cn(
        "glass relative flex flex-wrap items-center justify-between gap-3 p-4",
        isError
          ? "border-loss/40 bg-loss-bg/30 text-loss shadow-[0_0_24px_rgba(251,113,133,0.15)]"
          : "border-warn/40 bg-warn-bg/20 text-warn shadow-[0_0_24px_rgba(251,191,36,0.1)]",
        className,
      )}
    >
      <div className="flex items-center gap-2.5">
        {isError ? (
          <AlertCircle size={18} className="shrink-0 text-loss" />
        ) : (
          <Info size={18} className="shrink-0 text-warn" />
        )}
        <p className="text-body font-medium text-text-0">{message}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
