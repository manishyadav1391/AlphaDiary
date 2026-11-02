"use client";

import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/*
  Design spec §9.1:
  Primary: accent gradient, white text (always visible), 12px radius, inner highlight, hover glow.
  Secondary: glass-1 background, border glass-border, text-0.
  Ghost / Quiet: transparent, hover glass-2.
  Destructive: loss text/accent with subtle glass background.
*/
export const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none " +
    "transition-[transform,background,border-color,box-shadow,opacity] duration-200 ease-out " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 " +
    "disabled:pointer-events-none disabled:opacity-40 active:scale-[0.97] " +
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-[linear-gradient(135deg,#8b5cf6_0%,#6d28d9_100%)] text-white font-semibold " +
          "shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_8px_20px_-6px_rgba(139,92,246,0.5)] " +
          "hover:brightness-110 hover:-translate-y-0.5 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_12px_28px_-6px_rgba(139,92,246,0.65)] " +
          "active:translate-y-0 active:brightness-95",
        secondary:
          "glass glass--interactive text-text-0 hover:text-white border-glass-border hover:border-glass-border-strong",
        quiet:
          "text-text-1 hover:text-text-0 hover:bg-glass-2 rounded-sm",
        ghost:
          "text-text-1 hover:text-text-0 hover:bg-glass-2 rounded-sm",
        destructive:
          "bg-loss-bg/50 border border-loss/30 text-loss hover:bg-loss-bg hover:border-loss/60 shadow-[0_0_16px_rgba(251,113,133,0.15)]",
      },
      size: {
        lg: "h-12 rounded-[12px] px-6 text-body",
        md: "h-11 rounded-[12px] px-5 text-body",
        sm: "h-9 rounded-[10px] px-3.5 text-label",
        icon: "size-11 rounded-[12px]",
        "icon-sm": "size-9 rounded-[10px]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    loading?: boolean;
  };

export function Button({
  className,
  variant,
  size,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="size-4 animate-spin motion-reduce:hidden" />}
      <span className={cn("inline-flex items-center gap-2", loading && "opacity-80")}>
        {children}
      </span>
    </button>
  );
}
