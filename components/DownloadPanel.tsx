"use client";

import { Download } from "lucide-react";
import type { PipelineResult } from "@/lib/types";

// The only downloads we surface, in priority order. STEP is the CAD file for
// AutoCAD/FreeCAD, STL is the 3D mesh, DXF is the 2D outline.
const DOWNLOADS: { key: "step" | "stl" | "dxf"; label: string; accent?: boolean }[] = [
  { key: "step", label: "STEP", accent: true },
  { key: "stl", label: "STL" },
  { key: "dxf", label: "DXF" }
];

export function DownloadPanel({ result }: { result: PipelineResult | null }) {
  const files = (result?.files ?? {}) as Record<string, string>;
  const available = DOWNLOADS.filter((item) => files[item.key]);

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">Download</h2>

      {available.length > 0 ? (
        <div className="flex flex-wrap gap-2.5">
          {available.map((item) => (
            <Chip key={item.key} href={files[item.key]} label={item.label} accent={item.accent} />
          ))}
        </div>
      ) : (
        <p className="rounded-[14px] border border-dashed border-line bg-bone px-4 py-6 text-sm text-muted">
          Once you make a model, your STEP, STL, and DXF files show up here to download.
        </p>
      )}

      {result?.cadSummary && (
        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          <Stat label="Outline" value={result.cadSummary.detected_outline ? "Detected" : "None"} />
          <Stat label="Holes" value={String(result.cadSummary.detected_holes)} />
          <Stat
            label="Est. size (mm)"
            value={`${result.cadSummary.estimated_dimensions_mm.width} × ${result.cadSummary.estimated_dimensions_mm.height} × ${result.cadSummary.estimated_dimensions_mm.thickness}`}
          />
        </div>
      )}

      {result?.warnings && result.warnings.length > 0 && (
        <details className="mt-4 rounded-[12px] border border-line bg-bone px-4 py-3 text-sm text-muted">
          <summary className="cursor-pointer select-none font-medium text-ink">
            Notes ({result.warnings.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {result.warnings.map((warning) => (
              <li key={warning} className="leading-6">
                {warning}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function Chip({ href, label, accent }: { href: string; label: string; accent?: boolean }) {
  return (
    <a
      href={href}
      download
      target="_blank"
      rel="noreferrer"
      className={`group inline-flex items-center gap-2 rounded-full border px-5 py-2.5 text-sm font-medium transition duration-200 hover:-translate-y-0.5 hover:shadow-md ${
        accent
          ? "border-accent/40 bg-accent/10 text-accent hover:bg-accent/15"
          : "border-line bg-card text-ink hover:border-accent/50 hover:text-accent"
      }`}
    >
      <Download className="h-4 w-4 transition-transform duration-200 group-hover:translate-y-0.5" aria-hidden />
      {label}
    </a>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[12px] border border-line bg-bone px-3.5 py-2.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}
