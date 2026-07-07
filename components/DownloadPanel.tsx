"use client";

import { Download, Wrench } from "lucide-react";
import type { PipelineResult } from "@/lib/types";

const labels: Record<string, string> = {
  stl: "Mesh STL",
  obj: "Mesh OBJ",
  glb: "Mesh GLB",
  step: "CAD STEP",
  dxf: "CAD DXF",
  cad_stl: "CAD STL"
};

export function DownloadPanel({ result }: { result: PipelineResult | null }) {
  const entries = Object.entries(result?.files ?? {}).filter(
    (entry): entry is [string, string] => Boolean(entry[1]) && entry[0] !== "freecad_step" && entry[0] !== "freecad_obj"
  );
  const freecadStep = result?.freecad?.step;
  const freecadObj = result?.freecad?.obj;

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

      {(freecadStep || freecadObj) && (
        <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Wrench className="h-5 w-5 text-blue-700" aria-hidden />
            <h3 className="font-semibold text-blue-900">Open in FreeCAD</h3>
          </div>
          <p className="mb-3 text-sm leading-6 text-blue-900">
            Download the FreeCAD-ready file below, then in FreeCAD choose <strong>File &rarr; Open</strong> and select it.
            STEP preserves solid geometry for editing; OBJ is a mesh you can import with the Mesh workbench.
          </p>
          <div className="flex flex-wrap gap-3">
            {freecadStep && (
              <a
                href={freecadStep}
                download
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
              >
                <Download className="h-4 w-4" aria-hidden />
                Download for FreeCAD (.step)
              </a>
            )}
            {freecadObj && (
              <a
                href={freecadObj}
                download
                className="inline-flex items-center gap-2 rounded-md border border-blue-300 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 transition hover:border-blue-500"
              >
                <Download className="h-4 w-4" aria-hidden />
                Download for FreeCAD (.obj)
              </a>
            )}
          </div>
        </div>
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

      {result?.warnings && result.warnings.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm text-amber-700">
          {result.warnings.map((warning) => (
            <li key={warning}>&bull; {warning}</li>
          ))}
        </ul>
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
