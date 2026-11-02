"use client";

import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCount, formatDateShort, formatTime } from "@/lib/format";
import { useNotificationLog, useSyncLogs } from "@/lib/queries";

/*
  FR-REM-14 and the sync history the manual points at ("Settings → sync
  history (not built yet)").

  The statuses matter more than they look: `skipped_no_token` is the trace of a
  trading day whose fills can now only be recovered from a Console CSV, and
  `skipped_token_valid` is the reminder system correctly staying quiet.
*/

const SYNC_TONE: Record<string, "profit" | "loss" | "marker" | "default"> = {
  success: "profit",
  partial: "marker",
  failed: "loss",
  skipped_no_token: "loss",
  running: "default",
};

const NOTIFY_TONE: Record<string, "profit" | "loss" | "marker" | "default"> = {
  sent: "profit",
  failed: "loss",
  skipped_token_valid: "default",
  skipped_user: "default",
};

function when(value: string | null): string {
  if (!value) return "–";
  return `${formatDateShort(value)} ${formatTime(value)}`;
}

export function ActivityLog() {
  const syncs = useSyncLogs();
  const notifications = useNotificationLog();

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h3 className="text-h3 text-text-0">Sync history</h3>
        {syncs.isLoading ? (
          <Skeleton className="h-40 w-full rounded-[12px]" />
        ) : !syncs.data || syncs.data.length === 0 ? (
          <p className="text-body text-text-2">Nothing has synced yet.</p>
        ) : (
          <div className="overflow-hidden rounded-[12px] border border-glass-border bg-glass-1">
            {syncs.data.map((log) => (
              <div
                key={log.id}
                className="flex flex-wrap items-center gap-3 border-b border-glass-border px-3 py-2 last:border-b-0"
              >
                <span className="font-mono text-mono-sm text-text-2">{when(log.started_at)}</span>
                <Chip tone={SYNC_TONE[log.status] ?? "default"}>{log.status}</Chip>
                <span className="text-caption text-text-2">{log.trigger}</span>
                {log.error && (
                  <span className="text-caption text-loss">{log.error}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-h3 text-text-0">Reminder log</h3>
        <p className="text-body text-text-2">
          One row per slot and channel.{" "}
          <span className="font-mono text-mono-sm">skipped_token_valid</span> means you were
          already connected and nothing needed sending.
        </p>
        {notifications.isLoading ? (
          <Skeleton className="h-40 w-full rounded-[12px]" />
        ) : !notifications.data || notifications.data.length === 0 ? (
          <p className="text-body text-text-2">
            No reminders have been evaluated yet. If that is unexpected, check that the worker
            container is running.
          </p>
        ) : (
          <div className="overflow-hidden rounded-[12px] border border-glass-border bg-glass-1">
            {notifications.data.map((row) => (
              <div
                key={row.id}
                className="flex flex-wrap items-center gap-3 border-b border-glass-border px-3 py-2 last:border-b-0"
              >
                <span className="font-mono text-mono-sm text-text-2">{row.slot_key}</span>
                <Chip tone={NOTIFY_TONE[row.status] ?? "default"}>{row.status}</Chip>
                <span className="text-caption text-text-2">{row.channel}</span>
                {row.attempts > 1 && (
                  <span className="text-caption text-text-2">
                    {formatCount(row.attempts)} attempts
                  </span>
                )}
                {row.error && <span className="text-caption text-loss">{row.error}</span>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
