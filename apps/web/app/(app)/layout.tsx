"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { BottomNav, Sidebar } from "@/components/shell/nav";
import { Header } from "@/components/shell/header";
import { AuroraBackground } from "@/components/layout/aurora-background";
import { PageTransition } from "@/components/layout/page-transition";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useMe, useTrades } from "@/lib/queries";

/**
  Design spec §8:
  App shell with Aurora background, fixed collapsible glass sidebar,
  sticky glass header, mobile bottom nav, and animated page transitions.
*/
export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const me = useMe();
  const review = useTrades({ needs_review: true, limit: 1, intraday_only: false });

  const unauthorized = me.error instanceof ApiError && me.error.isUnauthorized;

  useEffect(() => {
    if (unauthorized) router.replace("/login");
  }, [unauthorized, router]);

  if (me.isLoading || unauthorized) {
    return (
      <div className="relative flex min-h-dvh flex-col overflow-hidden bg-bg-0">
        <AuroraBackground />
        <div className="h-16 border-b border-glass-border bg-bg-1/60 backdrop-blur-md" />
        <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-6 p-6">
          <Skeleton className="h-44 w-full rounded-[20px]" />
          <Skeleton className="h-28 w-full rounded-[20px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-dvh overflow-x-hidden bg-bg-0 text-text-0 selection:bg-violet-600/30 selection:text-white">
      {/* Background Aurora Blobs */}
      <AuroraBackground />

      {/* Desktop Sidebar */}
      <Sidebar reviewCount={review.data?.totals.trades ?? 0} />

      {/* Main Content Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1120px] flex-1 px-4 py-8 pb-28 md:px-8 lg:pb-12">
          <PageTransition>{children}</PageTransition>
        </main>
        {/* Mobile Bottom Tab Bar */}
        <BottomNav reviewCount={review.data?.totals.trades ?? 0} />
      </div>
    </div>
  );
}
