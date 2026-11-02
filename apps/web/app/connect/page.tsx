"use client";

import { RefreshCw, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { AuroraBackground } from "@/components/layout/aurora-background";
import { ApiError, api } from "@/lib/api";
import type { KiteLoginUrl } from "@/lib/types";
import { cn } from "@/lib/utils";

type State =
  | { kind: "starting" }
  | { kind: "unconfigured"; message: string }
  | { kind: "failed"; message: string };

export default function ConnectPage() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "starting" });
  const started = useRef(false);

  const start = useCallback(async () => {
    setState({ kind: "starting" });
    try {
      const { login_url } = await api.get<KiteLoginUrl>("/kite/login-url");
      window.location.assign(login_url);
    } catch (error) {
      if (error instanceof ApiError && error.isUnauthorized) {
        router.replace(`/login?next=${encodeURIComponent("/connect")}`);
        return;
      }
      if (error instanceof ApiError && error.code === "not_configured") {
        setState({ kind: "unconfigured", message: error.message });
        return;
      }
      setState({
        kind: "failed",
        message:
          error instanceof ApiError
            ? error.message
            : "Could not reach the server. Check that it is running.",
      });
    }
  }, [router]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start();
  }, [start]);

  return (
    <main className="relative flex min-h-dvh items-center justify-center bg-bg-0 px-4 overflow-hidden">
      <AuroraBackground />

      <div
        className="glass glass--strong relative z-10 flex w-full max-w-[420px] flex-col gap-6 p-8 shadow-2xl backdrop-blur-2xl rounded-[24px]"
        aria-live="polite"
      >
        <div className="flex size-12 items-center justify-center rounded-[14px] bg-[linear-gradient(135deg,#8b5cf6_0%,#6d28d9_100%)] shadow-[0_0_24px_rgba(139,92,246,0.6)]">
          <TrendingUp className="size-6 text-white" />
        </div>

        {state.kind === "starting" && (
          <div className="flex flex-col gap-3">
            <h1 className="text-h2 font-bold text-text-0">Connecting to Zerodha</h1>
            <p className="text-body text-text-2">
              Redirecting you to the secure Kite authentication gateway...
            </p>
            <div className="flex items-center gap-2 pt-2 text-violet-400">
              <RefreshCw size={18} aria-hidden className="animate-spin" />
              <span className="text-caption font-semibold">Opening portal</span>
            </div>
          </div>
        )}

        {state.kind === "unconfigured" && (
          <div className="flex flex-col gap-4">
            <h1 className="text-h2 font-bold text-text-0">Broker Not Configured</h1>
            <p className="text-body text-text-1">{state.message}</p>
            <div className="rounded-[12px] bg-glass-1 border border-glass-border p-3">
              <p className="text-caption text-text-2">Run on server:</p>
              <code className="font-mono text-caption text-violet-300">
                python -m app.cli set-kite-credentials
              </code>
            </div>
            <Link
              href="/"
              className={cn(buttonVariants({ variant: "secondary", size: "md" }), "w-full text-center")}
            >
              Back to dashboard
            </Link>
          </div>
        )}

        {state.kind === "failed" && (
          <div className="flex flex-col gap-4">
            <h1 className="text-h2 font-bold text-text-0">Connection Failed</h1>
            <p role="alert" className="rounded-[10px] bg-loss-bg/30 border border-loss/40 p-3 text-caption font-medium text-loss">
              {state.message}
            </p>
            <Button variant="primary" size="lg" onClick={() => void start()}>
              Try connecting again
            </Button>
            <Link
              href="/"
              className={cn(buttonVariants({ variant: "quiet", size: "sm" }), "text-center text-text-2")}
            >
              Return to dashboard
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
