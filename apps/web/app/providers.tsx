"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

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

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
