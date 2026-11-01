"use client";

import { RefreshCw, Settings } from "lucide-react";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { useKiteStatus, useRunSync, useSyncStatus } from "@/lib/queries";
import { cn } from "@/lib/utils";

/*
  DESIGN.md 8: 56 px, not sticky. Left is the page title, or today's date on
  Home. Right is the connection chip, the sync button and the settings gear.
  No navigation links live here — those are the bottom tabs or the sidebar.
*/

const TITLES: Record<string, string> = {
  "/trades": "Trades",
  "/playbook": "Playbook",
  "/analytics": "Analytics",
};

function ConnectionChip() {
  const { data, isLoading } = useKiteStatus();
  const sync = useSyncStatus();

  if (isLoading) {
    return <span className="text-secondary text-slate">Checking…</span>;
  }

  if (sync.data?.running) {
    return (
      <span className="flex items-center gap-2 text-secondary text-slate">
        <RefreshCw size={14} className="motion-safe:animate-spin" aria-hidden />
        Syncing
      </span>
    );
  }

  const connected = data?.status === "connected";
  return (
    <span
      // Login needed gets the soft marker background: it is one of the
      // "needs attention" cases the highlighter exists for.
      className={cn(
        "flex items-center gap-2 rounded-[6px] px-2 py-1 text-secondary",
        connected ? "text-slate" : "bg-marker-soft text-graphite",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          connected ? "bg-profit" : "bg-loss",
        )}
      />
      {connected ? "Connected" : "Login needed"}
    </span>
  );
}

export function Header() {
  const pathname = usePathname();
  const runSync = useRunSync();
  const title = TITLES[pathname];

  return (
    <header className="flex h-14 items-center justify-between gap-3 border-b border-rule
      bg-sheet px-4 md:px-6">
      <h1 className="text-title text-graphite">
        {title ?? formatDate(new Date())}
      </h1>

      <div className="flex items-center gap-1">
        <ConnectionChip />

        <Button
          variant="quiet"
          size="icon"
          onClick={() => runSync.mutate()}
          disabled={runSync.isPending}
          // The verb matches the toast it produces (DESIGN.md 13).
          aria-label="Sync now"
          title="Sync now"
        >
          <RefreshCw
            size={20}
            strokeWidth={1.75}
            className={cn(runSync.isPending && "motion-safe:animate-spin")}
            aria-hidden
          />
        </Button>

        <Button variant="quiet" size="icon" aria-label="Settings" title="Settings" disabled>
          <Settings size={20} strokeWidth={1.75} aria-hidden />
        </Button>
      </div>
    </header>
  );
}
