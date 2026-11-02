import type { ReactNode } from "react";
import { AlertTriangle, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
  Design spec §9.10:
  Empty state with floating glass orb/icon and primary action.
  Error state as rose-tinted glass card with Retry.
 */
export function EmptyState({
  title,
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="glass flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <div className="relative mb-2 flex size-14 items-center justify-center rounded-full bg-violet-600/10 border border-violet-400/20 shadow-[0_0_24px_rgba(139,92,246,0.2)] motion-safe:animate-[bounce_4s_ease-in-out_infinite]">
        <Compass className="size-6 text-violet-400" />
      </div>
      {title && <h3 className="text-h3 font-semibold text-text-0">{title}</h3>}
      <p className="max-w-md text-body text-text-1">{message}</p>
      {action && (
        <div className="mt-2">
          <Button onClick={action.onClick} variant="primary" size="md">
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="glass flex flex-col items-center justify-center gap-3 border-loss/30 bg-loss-bg/30 px-6 py-10 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-loss-bg border border-loss/40 text-loss">
        <AlertTriangle className="size-5" />
      </div>
      <p className="text-body font-medium text-text-0">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
          Try again
        </Button>
      )}
    </div>
  );
}

export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3.5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-h2 font-semibold text-text-0">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
