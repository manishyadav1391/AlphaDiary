"use client";

import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { useId } from "react";

import { cn } from "@/lib/utils";

/*
  DESIGN.md 9 and 15: 48 px high, white, 1 px rule border, radius 6, 16 px
  text. Every field has a visible label — never a placeholder standing in for
  one — and errors read below the field.
*/

const control =
  "h-12 w-full rounded-[6px] border border-rule bg-sheet px-3 text-body " +
  "text-graphite placeholder:text-slate/70 disabled:opacity-50";

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
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-secondary text-slate">
        {label}
      </label>
      {children(id, messageId)}
      {(error || hint) && (
        <p id={messageId} className={cn("text-secondary", error ? "text-loss" : "text-slate")}>
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
      className={cn(control, invalid && "border-loss", className)}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}

export function NumberInput({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      // Brings up the decimal keypad on phones (DESIGN.md 9).
      inputMode="decimal"
      className={cn(control, "tabular text-right", className)}
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
        // Long text caps at about 70 characters a line (DESIGN.md 6).
        "h-auto min-h-24 max-w-[70ch] resize-y py-3 leading-6",
        className,
      )}
      {...props}
    />
  );
}
