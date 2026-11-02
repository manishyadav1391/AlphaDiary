"use client";

import { useState } from "react";
import { BarChart3, BookOpen, ChevronLeft, ChevronRight, Home, List, TrendingUp, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";

import { cn } from "@/lib/utils";

/*
  Design spec §8.1:
  Glass sidebar with sliding active indicator (layoutId),
  collapsible state with localStorage persistence,
  Trades count badge with spring pop,
  Analytics disabled status with "Soon" pill,
  and bottom glass tab bar on mobile.
*/

export const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/trades", label: "Trades", icon: List },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/playbook", label: "Playbook", icon: BookOpen },
  // The only way to recover a trading day missed without a Zerodha login
  // (FR-IMP). Belongs under Settings once that screen exists.
  { href: "/import", label: "Import", icon: Upload },
] as const;

export function BottomNav({ reviewCount = 0 }: { reviewCount?: number }) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main navigation"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-glass-border bg-bg-1/80 backdrop-blur-xl
        pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <div className="mx-auto flex max-w-[1120px] items-stretch justify-around px-2 py-1">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const disabled = "disabled" in item && item.disabled;
          const Icon = item.icon;

          if (disabled) {
            return (
              <span
                key={item.href}
                className="flex flex-1 flex-col items-center justify-center py-2 opacity-40 select-none cursor-not-allowed"
                aria-disabled="true"
              >
                <Icon size={20} strokeWidth={1.75} className="text-text-2" />
                <span className="text-[11px] text-text-2 mt-0.5">{item.label}</span>
              </span>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "relative flex flex-1 flex-col items-center justify-center py-2 transition-colors select-none",
                active ? "text-violet-400 font-semibold" : "text-text-1 hover:text-text-0",
              )}
              aria-current={active ? "page" : undefined}
            >
              <div className="relative">
                <Icon size={20} strokeWidth={active ? 2.2 : 1.75} />
                {item.href === "/trades" && reviewCount > 0 && (
                  <span className="absolute -top-1 -right-2 flex size-4 items-center justify-center rounded-full bg-violet-600 text-[9px] font-bold text-white shadow-[0_0_8px_rgba(139,92,246,0.6)]">
                    {reviewCount}
                  </span>
                )}
              </div>
              <span className="text-[11px] mt-0.5">{item.label}</span>
              {active && (
                <motion.div
                  layoutId="bottom-nav-dot"
                  className="absolute bottom-1 size-1 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.8)]"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function Sidebar({ reviewCount = 0 }: { reviewCount?: number }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("sidebar:collapsed") === "true";
  });

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar:collapsed", String(next));
  };

  return (
    <aside
      aria-label="Sidebar navigation"
      className={cn(
        "hidden shrink-0 flex-col justify-between border-r border-glass-border bg-bg-1/80 backdrop-blur-xl transition-[width] duration-300 ease-out lg:flex",
        collapsed ? "w-[80px]" : "w-[264px]",
      )}
    >
      <div className="flex flex-col gap-6 p-4">
        {/* Brand / Logo */}
        <div className="flex items-center justify-between px-2 pt-2">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-[linear-gradient(135deg,#8b5cf6_0%,#6d28d9_100%)] shadow-[0_0_16px_rgba(139,92,246,0.5)]">
              <TrendingUp className="size-5 text-white" />
            </div>
            {!collapsed && (
              <span className="truncate text-h3 font-semibold text-text-0 tracking-tight">
                Trading journal
              </span>
            )}
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex flex-col gap-1.5" aria-label="Main">
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const disabled = "disabled" in item && item.disabled;
            const Icon = item.icon;

            if (disabled) {
              return (
                <div
                  key={item.href}
                  className={cn(
                    "relative flex h-12 items-center gap-3 rounded-[12px] px-3.5 opacity-40 select-none cursor-not-allowed",
                    collapsed && "justify-center px-0",
                  )}
                  title="Coming soon"
                  aria-disabled="true"
                >
                  <Icon size={20} strokeWidth={1.75} className="text-text-2 shrink-0" />
                  {!collapsed && (
                    <div className="flex w-full items-center justify-between">
                      <span className="text-body text-text-2">{item.label}</span>
                      <span className="rounded-full bg-glass-2 px-2 py-0.5 text-[10px] text-text-2">
                        Soon
                      </span>
                    </div>
                  )}
                </div>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex h-12 items-center gap-3 rounded-[12px] px-3.5 transition-all select-none",
                  collapsed && "justify-center px-0",
                  active
                    ? "text-text-0 font-semibold"
                    : "text-text-1 hover:text-text-0 hover:bg-glass-2",
                )}
                aria-current={active ? "page" : undefined}
              >
                {/* Sliding active pill indicator (spec §8.1) */}
                {active && (
                  <motion.div
                    layoutId="sidebar-active-pill"
                    className="absolute inset-0 rounded-[12px] bg-violet-600/15 border border-violet-500/30 shadow-[inset_0_0_12px_rgba(139,92,246,0.15)]"
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  >
                    <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.8)]" />
                  </motion.div>
                )}

                <div className="relative z-10 flex items-center justify-center">
                  <Icon
                    size={20}
                    strokeWidth={active ? 2.2 : 1.75}
                    className="transition-transform duration-200 group-hover:translate-x-0.5"
                  />
                  {item.href === "/trades" && reviewCount > 0 && collapsed && (
                    <span className="absolute -top-1 -right-1 size-2 rounded-full bg-violet-500" />
                  )}
                </div>

                {!collapsed && (
                  <div className="relative z-10 flex w-full items-center justify-between">
                    <span className="text-body">{item.label}</span>
                    {item.href === "/trades" && reviewCount > 0 && (
                      <motion.span
                        initial={{ scale: 0.6 }}
                        animate={{ scale: 1 }}
                        transition={{ type: "spring", stiffness: 400, damping: 20 }}
                        className="flex h-5 min-w-5 items-center justify-center rounded-full bg-violet-600 px-1.5 text-caption font-bold text-white shadow-[0_0_10px_rgba(139,92,246,0.5)] tabular"
                      >
                        {reviewCount}
                      </motion.span>
                    )}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Collapse toggle at bottom */}
      <div className="border-t border-glass-border p-3">
        <button
          type="button"
          onClick={toggleCollapse}
          className="flex h-10 w-full items-center justify-center gap-2 rounded-[10px] text-text-2 hover:bg-glass-2 hover:text-text-0 transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight size={18} />
          ) : (
            <div className="flex w-full items-center justify-between px-2">
              <span className="text-label text-text-2">Collapse</span>
              <ChevronLeft size={18} />
            </div>
          )}
        </button>
      </div>
    </aside>
  );
}
