"use client";

import { BarChart3, BookOpen, Home, List } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/*
  DESIGN.md 8 and SCREENS.md 12. Four items, bottom tabs below 1024 px and a
  left sidebar above it. Settings lives in the header because it is used
  rarely, so it is deliberately not here.
*/
export const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/trades", label: "Trades", icon: List },
  { href: "/analytics", label: "Analytics", icon: BarChart3, disabled: true },
  { href: "/playbook", label: "Playbook", icon: BookOpen },
] as const;

function useActive(href: string): boolean {
  const pathname = usePathname();
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

function NavIcon({
  icon: Icon,
  active,
}: {
  icon: (typeof NAV_ITEMS)[number]["icon"];
  active: boolean;
}) {
  return (
    <span
      className={cn(
        "flex h-7 w-10 items-center justify-center rounded-[14px]",
        // The marker pill behind the active icon is one of the four places
        // the highlighter is allowed (DESIGN.md principle 3).
        active && "bg-marker",
      )}
    >
      <Icon size={22} strokeWidth={1.75} aria-hidden />
    </span>
  );
}

function Item({
  item,
  layout,
  badge,
}: {
  item: (typeof NAV_ITEMS)[number];
  layout: "tab" | "sidebar";
  badge?: number;
}) {
  const active = useActive(item.href);
  const disabled = "disabled" in item && item.disabled;

  const content = (
    <>
      <span className="relative">
        <NavIcon icon={item.icon} active={active} />
        {badge ? (
          <span
            className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center
              rounded-full bg-graphite px-1 text-caption text-white tabular"
          >
            {badge}
          </span>
        ) : null}
      </span>
      <span className={cn("text-caption", active && "font-semibold")}>{item.label}</span>
    </>
  );

  const shared = cn(
    "flex items-center gap-2",
    active ? "text-graphite" : "text-slate",
    layout === "tab" && "h-14 flex-1 flex-col justify-center gap-0.5",
    layout === "sidebar" && "h-12 rounded-[10px] px-3 hover:bg-fog",
    disabled && "pointer-events-none opacity-40",
  );

  if (disabled) {
    return (
      <span className={shared} aria-disabled title="Not built yet">
        {content}
      </span>
    );
  }

  return (
    <Link href={item.href} className={shared} aria-current={active ? "page" : undefined}>
      {content}
    </Link>
  );
}

export function BottomNav({ reviewCount = 0 }: { reviewCount?: number }) {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-sheet
        pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <div className="mx-auto flex max-w-[1120px] items-stretch">
        {NAV_ITEMS.map((item) => (
          <Item
            key={item.href}
            item={item}
            layout="tab"
            badge={item.href === "/trades" ? reviewCount : undefined}
          />
        ))}
      </div>
    </nav>
  );
}

export function Sidebar({ reviewCount = 0 }: { reviewCount?: number }) {
  return (
    <nav
      aria-label="Main"
      className="hidden w-[232px] shrink-0 flex-col gap-1 border-r border-rule bg-sheet
        px-4 py-6 lg:flex"
    >
      <p className="px-3 pb-4 text-section text-graphite">Trading journal</p>
      {NAV_ITEMS.map((item) => (
        <Item
          key={item.href}
          item={item}
          layout="sidebar"
          badge={item.href === "/trades" ? reviewCount : undefined}
        />
      ))}
    </nav>
  );
}
