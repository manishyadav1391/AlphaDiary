"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ConnectionChip } from "@/components/shell/connection-chip";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { formatDate } from "@/lib/format";
import { useKiteStatus, useRunSync } from "@/lib/queries";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

/*
  Design spec §8.2:
  Sticky glass topbar with scroll-driven border and opacity,
  page title (h1), status chip, sync button with spin animation,
  and settings gear with hover rotation.
*/

const TITLES: Record<string, string> = {
  "/trades": "Trades",
  "/playbook": "Playbook",
  "/analytics": "Analytics",
  "/import": "Import",
  "/settings": "Settings",
};

export function Header() {
  const pathname = usePathname();
  const runSync = useRunSync();
  const kite = useKiteStatus();
  const toast = useToast();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 8);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const title = TITLES[pathname];
  const connected = kite.data?.status === "connected";
  const syncLabel = connected ? "Sync now" : "Connect Zerodha first";

  const handleSync = async () => {
    try {
      const res = await runSync.mutateAsync();
      const count = (res?.fills_new ?? 0);
      toast(`Synced ${count} ${count === 1 ? "trade" : "trades"}`);
    } catch {
      toast("Sync failed. Check broker status.", { variant: "error" });
    }
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-20 flex h-16 items-center justify-between gap-4 px-4 transition-all duration-200 md:px-8",
        scrolled
          ? "border-b border-glass-border bg-bg-1/80 backdrop-blur-xl shadow-lg"
          : "border-b border-transparent bg-bg-0/40 backdrop-blur-md",
      )}
    >
      <div className="flex flex-col">
        <h1 className="text-h2 font-bold tracking-tight text-text-0 md:text-h1">
          {title ?? formatDate(new Date())}
        </h1>
        {!title && (
          <span className="text-[11px] font-medium text-text-2 tracking-wide uppercase">
            Intraday Journal
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <ConnectionChip />

        {/* Sync Button */}
        <Button
          variant="quiet"
          size="icon-sm"
          onClick={handleSync}
          disabled={runSync.isPending || !connected}
          aria-label={syncLabel}
          title={syncLabel}
          className="hover:text-violet-300"
        >
          <RefreshCw
            size={18}
            strokeWidth={1.75}
            className={cn(
              "transition-transform",
              runSync.isPending && "animate-spin text-violet-400",
            )}
            aria-hidden
          />
        </Button>

        <ThemeToggle />

        {/* Settings Button */}
        <Link
          href="/settings"
          aria-label="Settings"
          title="Settings"
          className={cn(
            buttonVariants({ variant: "quiet", size: "icon-sm" }),
            "group hover:text-text-0",
          )}
        >
          <Settings
            size={18}
            strokeWidth={1.75}
            className="transition-transform duration-300 group-hover:rotate-45"
            aria-hidden
          />
        </Link>
      </div>
    </header>
  );
}
