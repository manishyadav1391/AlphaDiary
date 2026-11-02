"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ThemeProvider } from "@/components/theme/theme-provider";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";

/**
 * Data is fetched in the browser, not on the server.
 *
 * With `cacheComponents` on, a server-side session read cannot be part of the
 * static shell, so it would need `use cache: private` and a Suspense boundary
 * per route. Fetching from the client keeps the shell static and gives us the
 * loading, empty and error states DESIGN.md 3 asks for anyway.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: (failureCount, error) => {
              // Retrying an expired session just delays the redirect.
              if (error instanceof ApiError && error.isUnauthorized) return false;
              return failureCount < 2;
            },
          },
        },
      }),
  );

  // ToastProvider sits inside the query client so any client component can
  // call useToast() after a mutation.
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>{children}</ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
