"use client";

import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme, type ThemeChoice } from "@/components/theme/theme-provider";
import { Button } from "@/components/ui/button";

/**
 * Cycles light → dark → system.
 *
 * A three-way cycle rather than a switch, because "system" is a real third
 * state and hiding it would strand anyone whose OS flips at sunset. The
 * tooltip always names what the next press does, so the cycle is discoverable
 * without a menu.
 */
const NEXT: Record<ThemeChoice, ThemeChoice> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const LABEL: Record<ThemeChoice, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

export function ThemeToggle() {
  const { choice, setChoice } = useTheme();
  const Icon = choice === "light" ? Sun : choice === "dark" ? Moon : Monitor;

  return (
    <Button
      variant="quiet"
      size="icon-sm"
      onClick={() => setChoice(NEXT[choice])}
      aria-label={`Theme: ${LABEL[choice]}. Switch to ${LABEL[NEXT[choice]]}.`}
      title={`Theme: ${LABEL[choice]} — switch to ${LABEL[NEXT[choice]]}`}
    >
      <Icon size={18} strokeWidth={1.75} aria-hidden />
    </Button>
  );
}
