"use client";

import Link from "next/link";
import { useState } from "react";

import { FilePicker } from "@/components/import/file-picker";
import { ImportReport } from "@/components/import/import-report";
import { PreviewTable } from "@/components/import/preview-table";
import { CountsRow, DateRange, ProductSplit, Rejections } from "@/components/import/report-figures";
import { Button } from "@/components/ui/button";
import { Field, SelectInput } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useImportTradebook, usePreviewTradebook } from "@/lib/queries";
import type { ImportProduct } from "@/lib/types";

/*
  FR-IMP. Upload → preview → confirm → report (SCREENS.md 9).

  Zerodha's API returns only the current trading day, so a day missed without
  a login can be recovered here and nowhere else. The import is idempotent on
  (account_id, kite_trade_id), which is why re-uploading is safe and the UI
  says so rather than guarding it behind a dialog.

  "Undo import" from SCREENS.md is deliberately absent: there is no endpoint
  for it yet, and a disabled button would be worse than none.
*/

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "file_too_large":
        return "That file is over 20 MB. Export a shorter date range.";
      case "unreadable_file":
        return "That file is not readable text. Export it again from Console.";
      case "not_configured":
        return "Add your broker account before importing.";
      default:
        // invalid_tradebook names the missing column, which is the most
        // useful thing we could say.
        return error.message;
    }
  }
  return "Could not reach the server. Check that it is running.";
}

export function ImportWizard() {
  const [file, setFile] = useState<File | null>(null);
  const [product, setProduct] = useState<"" | ImportProduct>("");
  const [guardError, setGuardError] = useState<string | null>(null);

  const preview = usePreviewTradebook();
  const run = useImportTradebook();

  // Derived from the mutations rather than a separate state, so the step and
  // the data it renders can never disagree.
  const report = run.data;
  const checked = preview.data;

  function reset() {
    run.reset();
    preview.reset();
    setFile(null);
    setProduct("");
    setGuardError(null);
  }

  if (report) {
    return <ImportReport report={report} onReset={reset} />;
  }

  const error = guardError ?? (preview.isError ? messageFor(preview.error) : null);
  const importError = run.isError ? messageFor(run.error) : null;

  return (
    <div className="flex flex-col gap-6">
      {!checked && (
        <>
          <FilePicker
            file={file}
            disabled={preview.isPending}
            onPick={(picked) => {
              setGuardError(null);
              preview.reset();
              setFile(picked);
            }}
            onError={(message) => {
              setFile(null);
              setGuardError(message);
            }}
            onClear={() => {
              setFile(null);
              setGuardError(null);
              preview.reset();
            }}
          />

          {error && (
            <p role="alert" className="text-body text-loss">
              {error}
            </p>
          )}

          <Button
            size="lg"
            className="self-start"
            disabled={!file || preview.isPending}
            onClick={() => file && preview.mutate(file)}
          >
            {preview.isPending ? "Checking…" : "Check file"}
          </Button>

          {preview.isPending && <Skeleton className="h-64 w-full" />}
        </>
      )}

      {checked && file && (
        <>
          <div className="flex flex-col gap-1">
            <h2 className="text-h2 text-text-0">Checked {file.name}</h2>
            <DateRange from={checked.date_from} to={checked.date_to} />
          </div>

          {/* Only what preview() actually computes. rows_new, rows_dup and
              unresolved_symbols are filled by the import itself, so showing
              them here would report zero as fact. */}
          <CountsRow
            items={[
              { label: "Rows read", value: checked.rows_read },
              { label: "Rejected", value: checked.rows_rejected },
            ]}
          />

          <ProductSplit products={checked.products} />

          {checked.rows_without_timestamp > 0 && (
            <p className="text-body text-text-2">
              {formatCount(checked.rows_without_timestamp)} rows have no execution time. They
              import at the day&apos;s close.
            </p>
          )}

          {checked.columns.length > 0 && (
            <p className="text-label text-text-2">Detected columns: {checked.columns.join(", ")}</p>
          )}

          <PreviewTable rows={checked.preview} totalRows={checked.rows_read} />

          <Rejections rejections={checked.rejections} />

          <Field
            label="Product"
            hint="Console's tradebook has no product column, so the split above is inferred from
              whether each position flattened within its own day. Override it only when that
              split is wrong for the whole file."
          >
            {(id, describedBy) => (
              <SelectInput
                id={id}
                aria-describedby={describedBy}
                value={product}
                disabled={run.isPending}
                onChange={(event) => setProduct(event.target.value as "" | ImportProduct)}
                className="max-w-[320px]"
              >
                <option value="">Detected from the file</option>
                <option value="MIS">MIS (intraday)</option>
                <option value="CNC">CNC (delivery)</option>
                <option value="NRML">NRML (carry-forward)</option>
              </SelectInput>
            )}
          </Field>

          <p className="text-body text-text-2">
            Importing the same file twice is safe: duplicate rows are reported and nothing is
            added, so your P&amp;L cannot be double-counted.
          </p>

          {importError && (
            <p role="alert" className="text-body text-loss">
              {importError}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="lg"
              disabled={run.isPending || checked.rows_read === checked.rows_rejected}
              onClick={() => run.mutate({ file, product: product || undefined })}
            >
              {run.isPending ? "Importing…" : "Import"}
            </Button>
            <Button variant="quiet" size="md" onClick={reset} disabled={run.isPending}>
              Choose another file
            </Button>
          </div>

          {checked.rows_read === checked.rows_rejected && (
            <p className="text-body text-text-2">
              Every row was rejected, so there is nothing to import. Check that this is a Console
              tradebook export and not an order book or a P&amp;L statement.{" "}
              <Link href="/" className="underline">
                Back to home
              </Link>
            </p>
          )}
        </>
      )}
    </div>
  );
}
