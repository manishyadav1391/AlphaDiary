"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { BottomNav, Sidebar } from "@/components/shell/nav";
import { Header } from "@/components/shell/header";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useMe, useTrades } from "@/lib/queries";

/**
 * Everything inside this group needs a session.
 *
 * The API is the authority: a 401 from `/auth/me` means the cookie is gone or
 * expired, and the owner goes to the login screen. The client never tries to
 * read the session cookie itself, because it is HttpOnly and should be.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const me = useMe();
  // Drives the count badge on the Trades tab (DESIGN.md 8).
  const review = useTrades({ needs_review: true, limit: 1, intraday_only: false });

  const unauthorized = me.error instanceof ApiError && me.error.isUnauthorized;

  useEffect(() => {
    if (unauthorized) router.replace("/login");
  }, [unauthorized, router]);

  if (me.isLoading || unauthorized) {
    return (
      <div className="flex min-h-dvh flex-col">
        <div className="h-14 border-b border-rule bg-sheet" />
        <div className="flex flex-col gap-4 p-4">
          <Skeleton className="h-36 w-full rounded-[16px]" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh">
      <Sidebar reviewCount={review.data?.totals.trades ?? 0} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1120px] flex-1 px-4 pt-6 pb-24 md:px-6 lg:pb-10">
          {children}
        </main>
        <BottomNav reviewCount={review.data?.totals.trades ?? 0} />
      </div>
    </div>
  );
}
