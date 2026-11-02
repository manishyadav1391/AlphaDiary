"use client";

/*
  Motion utilities (spec §11).

  Shared animation variants, easings, the useCountUp hook for number
  tweening, and the confetti celebration function. All Framer Motion
  references go through this file so the motion library is never
  imported from page components directly.
*/

import { useEffect, useRef } from "react";
import { animate, useMotionValue, useTransform, type MotionValue } from "motion/react";
import { formatMoney } from "@/lib/format";

/* ---------- Easings ---------- */
export const easeOut = [0.22, 1, 0.36, 1] as const;
export const easeInOut = [0.65, 0, 0.35, 1] as const;
export const easeSpring = [0.34, 1.56, 0.64, 1] as const;

/* ---------- Stagger variants (spec §11.3) ---------- */
export const staggerContainer = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
};

export const staggerItem = {
  hidden: { opacity: 0, y: 16, filter: "blur(4px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.42, ease: easeOut },
  },
};

/* ---------- Page transition variants (spec §11.2) ---------- */
export const pageEnter = {
  initial: { opacity: 0, y: 12, filter: "blur(6px)" },
  animate: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -8 },
  transition: {
    enter: { duration: 0.48, ease: easeOut },
    exit: { duration: 0.18, ease: easeOut },
  },
};

/* ---------- Number count-up hook (spec §11.5) ---------- */
export function useCountUp(
  value: number,
  options: { duration?: number; format?: (v: number) => string } = {},
): MotionValue<string> {
  const { duration = 0.8, format = (v) => formatMoney(v, { signed: true }) } = options;
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => format(v));
  const prev = useRef(0);

  useEffect(() => {
    const from = prev.current;
    prev.current = value;
    mv.set(from);
    const controls = animate(mv, value, {
      duration,
      ease: easeOut as unknown as [number, number, number, number],
    });
    return controls.stop;
  }, [value, duration, mv]);

  return text;
}

/* ---------- Confetti celebration (spec §11.6) ---------- */
export async function celebrate(
  origin = { x: 0.5, y: 0.4 },
  size: "sm" | "md" = "md",
) {
  // Check reduced motion preference
  if (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return;
  }

  const confetti = (await import("canvas-confetti")).default;
  confetti({
    particleCount: size === "md" ? 120 : 60,
    spread: 70,
    startVelocity: 38,
    ticks: 180,
    origin,
    colors: ["#8b5cf6", "#a78bfa", "#c4b5fd", "#34d399", "#ffffff"],
    disableForReducedMotion: true,
  });
}

/**
 * Fire confetti once per day, tracked in localStorage.
 * Returns true if it fired, false if it was already fired today.
 */
export function celebrateOnce(key: string, origin?: { x: number; y: number }): boolean {
  if (typeof window === "undefined") return false;
  const storageKey = `confetti:${key}`;
  if (localStorage.getItem(storageKey)) return false;
  localStorage.setItem(storageKey, "1");
  void celebrate(origin);
  return true;
}

