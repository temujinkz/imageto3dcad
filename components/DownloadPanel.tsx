"use client";

import { Download } from "lucide-react";
import type { GeneratedResult } from "@/lib/types";

const labels: Record<string, string> = {
  stl: "Download STL",
  obj: "Download OBJ",
  glb: "Download GLB",
  step: "Download STEP",
  dxf: "Download DXF"
};

export function DownloadPanel({ result }: { result: GeneratedResult | null }) {
  const entries = Object.entries(result?.files ?? {}).filter((entry): entry is [string, string] => Boolean(entry[1]));

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Exports</p>
        <h2 className="text-2xl font-semibold text-ink">Download generated files</h2>
      </div>

      {entries.length > 0 ? (
        <div className="flex flex-wrap gap-3">
          {entries.map(([key, url]) => (
            <a
              key={key}
              href={url}
              target="_blank"
              rel="noreferrer"
              download
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:text-blue-700"
            >
              <Download className="h-4 w-4" aria-hidden />
              {labels[key] ?? `Download ${key.toUpperCase()}`}
            </a>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-600">
          STL, OBJ/GLB, STEP, and DXF download buttons appear here after generation.
        </p>
      )}

      {result?.cadSummary && (
        <div className="mt-5 grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 sm:grid-cols-3">
          <SummaryItem label="Outline detected" value={result.cadSummary.detected_outline ? "Yes" : "No"} />
          <SummaryItem label="Detected holes" value={String(result.cadSummary.detected_holes)} />
          <SummaryItem
            label="Estimated dimensions"
            value={`${result.cadSummary.estimated_dimensions_mm.width} x ${result.cadSummary.estimated_dimensions_mm.height} x ${result.cadSummary.estimated_dimensions_mm.thickness} mm`}
          />
        </div>
      )}

      <p className="mt-4 text-sm leading-6 text-slate-600">
        STEP/DXF are intended as editable CAD starting points. Accuracy depends on photo quality and object simplicity.
      </p>
    </section>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-medium text-ink">{value}</p>
    </div>
  );
}
