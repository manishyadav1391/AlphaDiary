"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info";
type Toast = { id: number; message: string; variant?: ToastVariant };

type ShowToastFn = (message: string, options?: { variant?: ToastVariant }) => void;

const ToastContext = createContext<ShowToastFn>(() => {});

export function useToast(): ShowToastFn {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show: ShowToastFn = useCallback((message, options) => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ id: Date.now(), message, variant: options?.variant ?? "success" });
    timer.current = setTimeout(() => setToast(null), 4_000);
  }, []);

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  }, []);

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2 p-4"
        role="status"
        aria-live="polite"
      >
        <AnimatePresence>
          {toast && (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 16, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.95 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className={cn(
                "pointer-events-auto relative flex items-center justify-between gap-3 overflow-hidden rounded-[16px] p-4 pr-3",
                "glass glass--strong border-glass-border-strong text-text-0 shadow-[0_20px_48px_-16px_rgba(0,0,0,0.8)] backdrop-blur-xl",
              )}
            >
              <div className="flex items-center gap-3">
                {toast.variant === "error" ? (
                  <AlertCircle className="size-5 shrink-0 text-loss" />
                ) : toast.variant === "info" ? (
                  <Info className="size-5 shrink-0 text-info" />
                ) : (
                  <CheckCircle2 className="size-5 shrink-0 text-profit" />
                )}
                <p className="text-body font-medium">{toast.message}</p>
              </div>

              <button
                type="button"
                onClick={dismiss}
                aria-label="Dismiss toast"
                className="text-text-2 hover:text-text-0 rounded-sm p-1 transition-colors"
              >
                <X className="size-4" />
              </button>

              {/* Progress bar animation */}
              <div
                className="absolute bottom-0 left-0 h-[2px] w-full bg-violet-500/40"
                style={{
                  animation: "toast-progress 4s linear forwards",
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
