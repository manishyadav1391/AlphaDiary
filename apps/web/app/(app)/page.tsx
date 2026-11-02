"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";

import { LowSampleNote } from "@/components/common/low-sample";
import { Banner } from "@/components/shell/banner";
import { EmptyState, Section } from "@/components/common/states";
import { CalendarHeatmap } from "@/components/dashboard/calendar";
import { EquityCurveChart } from "@/components/dashboard/equity-curve";
import {
  MonthPicker,
  currentMonth,
  monthRange,
} from "@/components/dashboard/month-picker";
import { TodayCard } from "@/components/dashboard/today-card";
import { TradeRow } from "@/components/trades/trade-row";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { LOGIN_NEEDED, kiteErrorMessage } from "@/lib/kite";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
  keys,
  useEquityCurve,
  useHeatmap,
  useKiteStatus,
  useRunSync,
  useSummary,
  useSyncStatus,
  useTrades,
} from "@/lib/queries";

/** What the Kite callback just told us, held across the URL cleanup. */
type Flash = { kind: "connected" } | { kind: "error"; code: string };

/** Home (spec §10.1, FR-DASH). */
function HomeContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  // The month lives in the URL so the view is bookmarkable
  const month = params.get("month") ?? currentMonth();
  const { from, to } = monthRange(month);

  const summary = useSummary(from, to);
  const heatmap = useHeatmap(month);
  const curve = useEquityCurve(from, to, "day");
  const sync = useSyncStatus();
  const kite = useKiteStatus();
  const runSync = useRunSync();
  const recent = useTrades({ status: "closed", limit: 10, intraday_only: false });

  const toast = useToast();
  const client = useQueryClient();
  const connectedParam = params.get("connected");
  const errorParam = params.get("kite_error");

  // Captured once, at mount, while the param is still in the URL. A lazy
  // initializer rather than an effect: setting state from an effect body
  // cascades a second render for something already known on the first.
  const [flash, setFlash] = useState<Flash | null>(() => {
    if (errorParam) return { kind: "error", code: errorParam };
    if (connectedParam) return { kind: "connected" };
    return null;
  });
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    if (!connectedParam && !errorParam) return;
    handled.current = true;

    if (!errorParam) {
      toast("Zerodha connected");
      void client.invalidateQueries({ queryKey: keys.kiteStatus });
      void client.invalidateQueries({ queryKey: keys.syncStatus });
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["trades"] });
    }

    router.replace(month === currentMonth() ? "/" : `/?month=${month}`);
  }, [connectedParam, errorParam, month, router, client, toast]);

  const wasRunning = useRef(false);
  const running = sync.data?.running ?? false;
  useEffect(() => {
    if (wasRunning.current && !running) {
      void client.invalidateQueries({ queryKey: ["dashboard"] });
      void client.invalidateQueries({ queryKey: ["trades"] });
    }
    wasRunning.current = running;
  }, [running, client]);

  function setMonth(next: string) {
    setSelectedDay(null);
    router.replace(next === currentMonth() ? "/" : `/?month=${next}`);
  }

  function openDay(date: string) {
    setSelectedDay(date);
    router.push(`/trades?date_from=${date}&date_to=${date}`);
  }

  const isMonthEmpty = summary.data?.trades === 0;

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      className="flex flex-col gap-10"
    >
      {/* Kite Status Banner */}
      {flash?.kind === "error" ? (
        <Banner
          tone="error"
          message={kiteErrorMessage(flash.code)}
          actions={
            <>
              <Link
                href="/connect"
                className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
              >
                Connect again
              </Link>
              <Button variant="quiet" size="sm" onClick={() => setFlash(null)}>
                Dismiss
              </Button>
            </>
          }
        />
      ) : (
        kite.data &&
        kite.data.status !== "connected" && (
          <Banner
            message={LOGIN_NEEDED}
            actions={
              <Link href="/connect" className={cn(buttonVariants({ size: "sm" }))}>
                Connect Zerodha
              </Link>
            }
          />
        )
      )}

      {/* Section A: Month Bar */}
      <motion.div variants={staggerItem} className="flex flex-wrap items-center justify-between gap-3">
        <MonthPicker month={month} onChange={setMonth} />
      </motion.div>

      {/* Section B: Month Summary & KPI Strip */}
      <motion.div variants={staggerItem}>
        <TodayCard
          data={summary.data}
          sync={sync.data}
          isLoading={summary.isLoading}
          month={month}
          onSync={() => runSync.mutate()}
        />
        {summary.data?.low_sample && (
          <div className="mt-3">
            <LowSampleNote trades={summary.data.trades} />
          </div>
        )}
      </motion.div>

      {/* Section C: Calendar Heatmap */}
      <motion.div variants={staggerItem}>
        <Section title="Calendar Heatmap">
          <CalendarHeatmap
            data={heatmap.data}
            isLoading={heatmap.isLoading}
            selected={selectedDay}
            onSelect={openDay}
          />
        </Section>
      </motion.div>

      {/* Section D: Equity Curve */}
      <motion.div variants={staggerItem}>
        <Section title="Equity Curve">
          <EquityCurveChart data={curve.data} isLoading={curve.isLoading} />
        </Section>
      </motion.div>

      {/* Section E: Recent Trades */}
      <motion.div variants={staggerItem}>
        <Section
          title="Recent Trades"
          action={
            <Link
              href="/trades"
              className="inline-flex items-center gap-1.5 text-label font-semibold text-violet-400 hover:text-violet-300 transition-colors"
            >
              <span>View all trades</span>
              <ArrowRight size={14} />
            </Link>
          }
        >
          {recent.isLoading ? (
            <Skeleton className="h-44 w-full rounded-[20px]" />
          ) : recent.data && recent.data.items.length > 0 ? (
            <div className="glass overflow-hidden rounded-[20px] shadow-sm">
              {/* Note addressing audit item 3 */}
              {isMonthEmpty && (
                <div className="border-b border-glass-border/60 bg-glass-1 px-4 py-2 text-[12px] text-text-2">
                  Showing recent trades across all sessions
                </div>
              )}
              {recent.data.items.map((trade) => (
                <TradeRow
                  key={trade.group_key}
                  trade={trade}
                  onOpen={() => router.push(`/trades?open=${encodeURIComponent(trade.group_key)}`)}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              message="No trades recorded yet. Connect your broker or run a sync."
              action={{ label: "View trades", onClick: () => router.push("/trades") }}
            />
          )}
        </Section>
      </motion.div>
    </motion.div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-[20px]" />}>
      <HomeContent />
    </Suspense>
  );
}
