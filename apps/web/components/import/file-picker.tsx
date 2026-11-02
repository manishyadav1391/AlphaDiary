"use client";

import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { MAX_IMPORT_BYTES, TOO_LARGE, formatFileSize } from "@/lib/import";

/*
  Step 1 of the wizard. The native file button cannot be styled to DESIGN.md
  9, so the real input is sr-only (still keyboard-reachable) and a Button
  drives it.
*/
export function FilePicker({
  file,
  onPick,
  onError,
  onClear,
  disabled,
}: {
  file: File | null;
  onPick: (file: File) => void;
  onError: (message: string) => void;
  onClear: () => void;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);

  function choose(picked: File | null | undefined) {
    if (!picked) return;
    if (picked.size === 0) {
      onError("That file is empty. Export it again from Console.");
      return;
    }
    if (picked.size > MAX_IMPORT_BYTES) {
      onError(TOO_LARGE);
      return;
    }
    onPick(picked);
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-text-2">
        In Zerodha Console, open Reports → Tradebook, pick a date range and download the CSV.
      </p>

      <input
        ref={input}
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        onChange={(event) => {
          const picked = event.target.files?.[0];
          // Cleared so picking the same file again still fires onChange.
          event.target.value = "";
          choose(picked);
        }}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="secondary"
          size="lg"
          disabled={disabled}
          onClick={() => input.current?.click()}
        >
          {file ? "Choose another file" : "Choose file"}
        </Button>

        {file && (
          <>
            <span className="text-body text-text-2">
              {file.name} · {formatFileSize(file.size)}
            </span>
            <Button type="button" variant="quiet" size="md" onClick={onClear} disabled={disabled}>
              Remove
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
