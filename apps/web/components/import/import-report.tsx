"use client";

import {
  CountsRow,
  ProductSplit,
  Rejections,
  UnresolvedSymbols,
} from "@/components/import/report-figures";
import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";
import type { ImportReport as Report } from "@/lib/types";

/*
  Step 4. Plain counts, never congratulatory (DESIGN.md 13).

  "Download report" is generated in the browser: there is no report endpoint,
  and the whole report is already in hand.
*/
function download(report: Report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `import-${report.batch_id?.slice(0, 8) ?? "report"}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

export function ImportReport({ report, onReset }: { report: Report; onReset: () => void }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="text-body text-text-0">
        Imported {formatCount(report.rows_new)} new rows.{" "}
        {report.rows_dup > 0 && `${formatCount(report.rows_dup)} were already there.`}
      </p>

      <CountsRow
        items={[
          { label: "Rows read", value: report.rows_read },
          { label: "New", value: report.rows_new },
          { label: "Duplicate", value: report.rows_dup },
          { label: "Rejected", value: report.rows_rejected },
        ]}
      />

      <ProductSplit products={report.products} />

      {report.reassigned_trade_ids > 0 && (
        <p className="text-body text-text-2">
          {formatCount(report.reassigned_trade_ids)} rows were reassigned to a different trade
          group.
        </p>
      )}

      <UnresolvedSymbols symbols={report.unresolved_symbols} />
      <Rejections rejections={report.rejections} />

      {report.batch_id && (
        <p className="text-mono-sm text-text-2">Batch {report.batch_id.slice(0, 8)}</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="md" onClick={() => download(report)}>
          Download report
        </Button>
        <Button variant="quiet" size="md" onClick={onReset}>
          Import another file
        </Button>
      </div>
    </div>
  );
}
