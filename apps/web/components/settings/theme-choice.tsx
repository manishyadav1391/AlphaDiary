"use client";

import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type ThemeChoice } from "@/components/theme/theme-provider";
import { cn } from "@/lib/utils";

const CHOICES: { id: ThemeChoice; label: string; hint: string; icon: typeof Sun }[] = [
  { id: "light", label: "Light", hint: "Paper. Easier in a bright room.", icon: Sun },
  { id: "dark", label: "Dark", hint: "The default. Easier at the close.", icon: Moon },
  { id: "system", label: "System", hint: "Follows your operating system.", icon: Monitor },
];

/** The same control as the header toggle, laid out so each option is named. */
export function ThemeChoiceRow() {
  const { choice, resolved, setChoice } = useTheme();

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-h3 text-text-0">Theme</h3>
        <p className="text-body text-text-2">
          Currently showing {resolved}. Stored in this browser only.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {CHOICES.map((item) => {
          const Icon = item.icon;
          const active = choice === item.id;
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={active}
              onClick={() => setChoice(item.id)}
              className={cn(
                "flex flex-col items-start gap-2 rounded-[12px] border p-4 text-left transition-colors",
                active
                  ? "border-violet-500/40 bg-violet-600/15"
                  : "border-glass-border bg-glass-1 hover:bg-glass-2",
              )}
            >
              <Icon size={20} strokeWidth={1.75} aria-hidden className="text-text-1" />
              <span className="text-body font-semibold text-text-0">{item.label}</span>
              <span className="text-caption text-text-2">{item.hint}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
