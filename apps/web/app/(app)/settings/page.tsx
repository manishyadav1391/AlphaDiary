"use client";

import { useState } from "react";

import { ActivityLog } from "@/components/settings/activity-log";
import { KiteSettings } from "@/components/settings/kite-settings";
import { ReminderSettings } from "@/components/settings/reminder-settings";
import { ThemeChoiceRow } from "@/components/settings/theme-choice";
import { cn } from "@/lib/utils";

/*
  FR-SET. Tabs rather than one long scroll: the three groups are consulted at
  completely different moments — Zerodha at setup, reminders when mail stops
  arriving, history when something looks wrong.
*/
const TABS = [
  { id: "zerodha", label: "Zerodha" },
  { id: "reminders", label: "Reminders" },
  { id: "history", label: "History" },
  { id: "appearance", label: "Appearance" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function SettingsPage() {
  const [tab, setTab] = useState<TabId>("zerodha");

  return (
    <div className="flex flex-col gap-6">
      <div role="tablist" aria-label="Settings sections" className="flex flex-wrap gap-1">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={cn(
              "h-10 rounded-[10px] px-4 text-body transition-colors",
              tab === item.id
                ? "border border-violet-500/30 bg-violet-600/15 font-semibold text-text-0"
                : "text-text-2 hover:bg-glass-2 hover:text-text-0",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" className="glass p-5 md:p-6">
        {tab === "zerodha" && <KiteSettings />}
        {tab === "reminders" && <ReminderSettings />}
        {tab === "history" && <ActivityLog />}
        {tab === "appearance" && <ThemeChoiceRow />}
      </div>
    </div>
  );
}
