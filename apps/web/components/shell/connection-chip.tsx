"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { expiryLabel } from "@/lib/kite";
import { useKiteStatus, useSyncStatus } from "@/lib/queries";
import { cn } from "@/lib/utils";

/*
  Design spec §8.2:
  Login status chip:
  - "Login needed": amber chip with pulsing dot, clickable.
  - "Connected": emerald dot, "Connected", static, with estimated expiry.
  - "Syncing": spinner with text.
*/
export function ConnectionChip() {
  const { data, isLoading } = useKiteStatus();
  const sync = useSyncStatus();

  if (isLoading) {
    return <span className="text-label text-text-2">Checking…</span>;
  }

  if (sync.data?.running) {
    return (
      <span
        className="flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-label font-medium text-violet-300"
        aria-live="polite"
      >
        <RefreshCw size={13} className="animate-spin text-violet-400" aria-hidden />
        Syncing
      </span>
    );
  }

  const connected = data?.status === "connected";
  const expiry = connected ? expiryLabel(data?.token_valid_until) : null;

  const detail = connected
    ? expiry
      ? `Estimated: ${expiry}`
      : "Connected to Zerodha"
    : (data?.message ?? "Log in to Zerodha to import today's trades");

  return (
    <div className="flex items-center gap-2" aria-live="polite">
      <div
        className={cn(
          "flex items-center gap-2 rounded-full px-3 py-1 text-label font-medium transition-all select-none",
          connected
            ? "border border-profit/30 bg-profit-bg text-profit shadow-[0_0_12px_rgba(52,211,153,0.15)]"
            : "border border-warn/40 bg-warn-bg text-warn shadow-[0_0_12px_rgba(251,191,36,0.2)]",
        )}
        title={detail}
        aria-label={connected ? `Zerodha connected. ${detail}` : "Zerodha login needed"}
      >
        {/* Pulsing or static dot */}
        <span
          aria-hidden
          className={cn(
            "size-2 rounded-full",
            connected ? "bg-profit" : "bg-warn pulse-dot",
          )}
        />
        {connected ? (
          <>
            <span className="md:hidden">Connected</span>
            <span className="hidden md:inline">Connected</span>
          </>
        ) : (
          <span className="font-semibold">Login needed</span>
        )}
      </div>

      {connected ? (
        expiry && (
          <span className="hidden font-mono text-caption text-text-2 md:inline">
            {expiry}
          </span>
        )
      ) : (
        <Link
          href="/connect"
          className={cn(
            buttonVariants({ variant: "primary", size: "sm" }),
            "h-8 px-3 text-caption font-semibold",
          )}
        >
          Connect
        </Link>
      )}
    </div>
  );
}
