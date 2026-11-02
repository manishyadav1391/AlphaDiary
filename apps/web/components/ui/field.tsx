"use client";

import { ChevronDown } from "lucide-react";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useId } from "react";

import { cn } from "@/lib/utils";

/*
  Design spec §9.4:
  Height 48px, glass-1 background (never plain white!),
  border glass-border, radius 12px, text-0, placeholder text-2.
  Focus: border violet-400, violet glow ring.
*/

const control =
  "h-12 w-full rounded-[12px] border border-glass-border bg-glass-1 px-4 text-body text-text-0 " +
  "placeholder:text-text-2 backdrop-blur-sm transition-all duration-200 " +
  "focus:border-violet-400/80 focus:bg-glass-2 focus:outline-none focus:ring-2 focus:ring-violet-400/40 focus:ring-offset-2 focus:ring-offset-bg-0 " +
  "disabled:opacity-40 disabled:cursor-not-allowed";

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string | null;
  hint?: string;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}) {
  const id = useId();
  const messageId = error || hint ? `${id}-message` : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-label text-text-2 font-medium tracking-wide">
        {label}
      </label>
      {children(id, messageId)}
      {(error || hint) && (
        <p id={messageId} className={cn("text-caption transition-opacity", error ? "text-loss" : "text-text-2")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}

export function TextInput({
  className,
  invalid,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={cn(control, invalid && "border-loss focus:ring-loss/40", className)}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}

export function NumberInput({
  className,
  prefix,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { prefix?: string }) {
  if (prefix) {
    return (
      <div className="relative flex items-center">
        <span className="pointer-events-none absolute left-4 text-text-2 font-mono select-none">
          {prefix}
        </span>
        <input
          inputMode="decimal"
          className={cn(control, "pl-9 tabular font-mono text-left", className)}
          {...props}
        />
      </div>
    );
  }

  return (
    <input
      inputMode="decimal"
      className={cn(control, "tabular font-mono text-left", className)}
      {...props}
    />
  );
}

export function TextArea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        control,
        "h-auto min-h-24 max-w-[70ch] py-3 leading-6 resize-y",
        className,
      )}
      {...props}
    />
  );
}

export function SelectInput({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        // Native, so phones get the OS picker and keyboard and screen-reader
        // behaviour come for free.
        className={cn(control, "appearance-none pr-11", className)}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        size={18}
        strokeWidth={1.75}
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-4 my-auto text-text-2"
      />
    </div>
  );
}
