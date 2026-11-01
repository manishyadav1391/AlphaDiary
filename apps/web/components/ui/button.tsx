"use client";

import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/*
  DESIGN.md 9. Primary is graphite with white text; there is no
  brand-coloured button. Labels state the action and never carry an arrow.
*/
const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium " +
    "transition-colors disabled:pointer-events-none disabled:opacity-50 " +
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-graphite text-white hover:bg-graphite/90",
        secondary: "bg-sheet border border-rule text-graphite hover:bg-fog",
        quiet: "text-slate hover:text-graphite hover:bg-fog",
        destructive: "bg-sheet border border-rule text-loss hover:bg-loss-1",
      },
      size: {
        // Primary actions are 48 px; touch targets never below 44 px.
        lg: "h-12 rounded-[10px] px-5 text-body",
        md: "h-11 rounded-[10px] px-4 text-row",
        icon: "size-11 rounded-[10px]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof button>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(button({ variant, size }), className)} {...props} />;
}
