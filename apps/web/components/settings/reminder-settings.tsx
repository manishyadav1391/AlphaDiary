"use client";

import { Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, SelectInput, TextInput } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import {
  useChannel,
  useReminderSettings,
  useSaveChannel,
  useSaveReminderSlots,
  useSkipRemindersToday,
  useTestChannel,
} from "@/lib/queries";
import type { ReminderSlot } from "@/lib/types";

/*
  FR-REM-02 and FR-REM-06.

  The email section is the one that matters operationally: if the destination
  is unset the worker logs `no_channels` once a minute and sends nothing, with
  no other sign that reminders are dead. Hence the explicit "Send test" and the
  blunt warning about Resend's verified-domain rule.
*/

function slotLabel(kind: string): string {
  return kind === "missed_sync" ? "Missed-sync alert" : "Reminder";
}

export function ReminderSettings() {
  const settings = useReminderSettings();
  const saveSlots = useSaveReminderSlots();
  const skipToday = useSkipRemindersToday();
  const toast = useToast();

  const [draft, setDraft] = useState<ReminderSlot[] | null>(null);
  const [seededFrom, setSeededFrom] = useState<ReminderSlot[] | null>(null);

  /*
    Seed the editable draft from the server's schedule, and re-seed whenever a
    genuinely new payload arrives. Adjusted during render rather than in an
    effect: React sanctions this for state derived from changing input, and it
    avoids the extra render an effect would cause. Comparing by reference is
    what we want — react-query hands back the same array until it refetches, so
    local edits are never clobbered mid-edit.
  */
  if (settings.data && settings.data.slots !== seededFrom) {
    setSeededFrom(settings.data.slots);
    setDraft(settings.data.slots);
  }

  if (settings.isLoading || draft === null) {
    return <Skeleton className="h-72 w-full rounded-[16px]" />;
  }

  if (settings.isError) {
    return (
      <p role="alert" className="text-body text-loss">
        {settings.error instanceof ApiError
          ? settings.error.message
          : "Could not load the reminder schedule."}
      </p>
    );
  }

  const data = settings.data;
  const dirty = JSON.stringify(draft) !== JSON.stringify(data?.slots ?? []);

  function update(index: number, patch: Partial<ReminderSlot>) {
    setDraft((current) =>
      current ? current.map((slot, i) => (i === index ? { ...slot, ...patch } : slot)) : current,
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-body text-text-2">
        All times are IST and only fire on trading days. A slot more than{" "}
        {data?.grace_minutes} minutes late is skipped, and nothing is sent between{" "}
        {data?.quiet_hours_start_ist} and {data?.quiet_hours_end_ist} unless a slot sits inside
        that window on purpose. The sync itself runs at {data?.sync_time_ist}.
      </p>

      <div className="flex flex-col gap-3">
        {draft.map((slot, index) => (
          <div
            key={`${slot.name}-${index}`}
            className="flex flex-wrap items-end gap-3 rounded-[12px] border border-glass-border bg-glass-1 p-3"
          >
            <label className="flex flex-col gap-1">
              <span className="text-label text-text-2">Time</span>
              <input
                type="time"
                value={slot.time}
                onChange={(event) => update(index, { time: event.target.value })}
                className="h-11 rounded-[10px] border border-glass-border bg-glass-1 px-3 font-mono text-mono-sm text-text-0 focus:border-violet-400 focus:outline-none"
              />
            </label>

            <label className="flex min-w-[140px] flex-1 flex-col gap-1">
              <span className="text-label text-text-2">Name</span>
              <TextInput
                value={slot.name}
                onChange={(event) => update(index, { name: event.target.value })}
                className="h-11"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-label text-text-2">Kind</span>
              <SelectInput
                value={slot.kind}
                onChange={(event) =>
                  update(index, { kind: event.target.value as ReminderSlot["kind"] })
                }
                className="h-11 w-[180px]"
              >
                <option value="reminder">Reminder</option>
                <option value="missed_sync">Missed-sync alert</option>
              </SelectInput>
            </label>

            <label className="flex items-center gap-2 pb-3">
              <input
                type="checkbox"
                checked={slot.enabled}
                onChange={(event) => update(index, { enabled: event.target.checked })}
                className="size-4 accent-violet-500"
              />
              <span className="text-body text-text-1">On</span>
            </label>

            <Button
              variant="quiet"
              size="icon-sm"
              aria-label={`Remove ${slot.name}`}
              title={`Remove ${slot.name}`}
              onClick={() => setDraft(draft.filter((_, i) => i !== index))}
            >
              <Trash2 size={16} aria-hidden />
            </Button>

            <Chip className="ml-auto">{slotLabel(slot.kind)}</Chip>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="md"
          onClick={() =>
            setDraft([
              ...draft,
              { name: `slot_${draft.length + 1}`, time: "15:00", kind: "reminder", enabled: true },
            ])
          }
        >
          <Plus size={16} aria-hidden />
          Add slot
        </Button>

        <Button
          size="md"
          disabled={!dirty || saveSlots.isPending}
          onClick={() =>
            saveSlots.mutate(draft, {
              onSuccess: () => toast("Schedule saved"),
            })
          }
        >
          {saveSlots.isPending ? "Saving…" : "Save schedule"}
        </Button>

        {dirty && (
          <Button variant="quiet" size="md" onClick={() => setDraft(data?.slots ?? [])}>
            Discard changes
          </Button>
        )}
      </div>

      {saveSlots.isError && (
        <p role="alert" className="text-body text-loss">
          {saveSlots.error instanceof ApiError
            ? saveSlots.error.message
            : "Could not save the schedule."}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-glass-border pt-4">
        <span className="text-body text-text-2">
          {data?.skipped_today
            ? "Reminders are silenced for the rest of today."
            : "Reminders are active for today."}
        </span>
        {!data?.skipped_today && (
          <Button
            variant="secondary"
            size="sm"
            disabled={skipToday.isPending}
            onClick={() => skipToday.mutate(undefined, { onSuccess: () => toast("Skipped today") })}
          >
            Skip today
          </Button>
        )}
      </div>

      <EmailChannel />
    </div>
  );
}

function EmailChannel() {
  const channel = useChannel("email");
  const save = useSaveChannel("email");
  const test = useTestChannel("email");
  const toast = useToast();

  const [destination, setDestination] = useState<string | null>(null);
  const [seededFrom, setSeededFrom] = useState<string | null | undefined>(undefined);

  // Same render-phase seeding as the schedule above.
  if (channel.data && channel.data.destination !== seededFrom) {
    setSeededFrom(channel.data.destination);
    setDestination(channel.data.destination ?? "");
  }

  if (channel.isLoading || destination === null) {
    return <Skeleton className="h-40 w-full rounded-[16px]" />;
  }

  const data = channel.data;

  return (
    <div className="flex flex-col gap-4 border-t border-glass-border pt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-h3 text-text-0">Email</h3>
        <Chip tone={data?.enabled && data?.configured ? "profit" : "marker"}>
          {data?.enabled && data?.configured ? "On" : "Off"}
        </Chip>
      </div>

      <p className="text-body text-text-2">
        Until you verify a domain with Resend, mail is sent from{" "}
        <span className="font-mono">onboarding@resend.dev</span> and Resend will{" "}
        <strong className="text-text-0">only</strong> deliver to the address your Resend account is
        registered under. Any other address is accepted by the API and never arrives — which is why
        the test button below is worth pressing.
      </p>

      <Field label="Send reminders to">
        {(id, describedBy) => (
          <TextInput
            id={id}
            aria-describedby={describedBy}
            type="email"
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
            autoComplete="email"
            spellCheck={false}
            className="max-w-[420px]"
          />
        )}
      </Field>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="md"
          disabled={save.isPending || !destination.trim()}
          onClick={() =>
            save.mutate(
              { enabled: true, destination: destination.trim() },
              { onSuccess: () => toast("Email reminders on") },
            )
          }
        >
          {save.isPending ? "Saving…" : "Save and enable"}
        </Button>

        {data?.enabled && (
          <Button
            variant="secondary"
            size="md"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { enabled: false, destination: destination.trim() || null },
                { onSuccess: () => toast("Email reminders off") },
              )
            }
          >
            Turn off
          </Button>
        )}

        <Button
          variant="secondary"
          size="md"
          disabled={test.isPending}
          onClick={() => test.mutate()}
        >
          <Send size={16} aria-hidden />
          {test.isPending ? "Sending…" : "Send test"}
        </Button>
      </div>

      {save.isError && (
        <p role="alert" className="text-body text-loss">
          {save.error instanceof ApiError ? save.error.message : "Could not save the channel."}
        </p>
      )}

      {/* FR-REM-06: show the result inline, with the exact error. */}
      {test.data && (
        <p
          role="status"
          className={cnTestTone(test.data.sent)}
        >
          {test.data.sent
            ? `Sent to ${test.data.destination ?? "the configured address"}. Check that inbox.`
            : `Not sent: ${test.data.error}`}
        </p>
      )}
    </div>
  );
}

function cnTestTone(sent: boolean): string {
  return sent ? "text-body text-profit" : "text-body text-loss";
}
