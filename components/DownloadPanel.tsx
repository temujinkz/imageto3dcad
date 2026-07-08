"use client";

import { Download } from "lucide-react";
import type { PipelineResult } from "@/lib/types";

// The Export section. Each entry resolves to the first available file key.
// Labels are exactly what the buttons read — the "Export" title already says these
// are export/download actions, so no "Download " prefix.
const EXPORTS: { label: string; keys: string[]; accent?: boolean }[] = [
  { label: "STEP", keys: ["step"] },
  // Mesh STL is the detailed 3D scan (matches the preview); cad_stl is the fallback.
  { label: "STL", keys: ["stl", "cad_stl"] },
  { label: "DXF", keys: ["dxf"] },
  // TODO: the backend has no dedicated AutoCAD/DWG artifact yet. STEP is the
  // AutoCAD-ready format (AutoCAD imports STEP natively); DXF is the 2D fallback.
  // Wire this to a real DWG export once the backend can produce one.
  { label: "Export to AutoCAD", keys: ["step", "dxf"], accent: true }
];

function resolveHref(files: Record<string, string>, keys: string[]): string | undefined {
  for (const key of keys) {
    if (files[key]) return files[key];
  }
  return undefined;
}

export function DownloadPanel({ result }: { result: PipelineResult | null }) {
  const files = (result?.files ?? {}) as Record<string, string>;
  const items = EXPORTS.map((item) => ({ ...item, href: resolveHref(files, item.keys) }));
  const anyAvailable = items.some((item) => item.href);

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">Export</h2>

      {result && !anyAvailable ? (
        <p className="rounded-[14px] border border-dashed border-line bg-bone px-4 py-6 text-sm text-muted">
          Model failed to generate. Try a clearer photo of a simple object.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2.5">
          {items.map((item) => (
            <ExportButton key={item.label} href={item.href} label={item.label} accent={item.accent} />
          ))}
        </div>
      )}
    </section>
  );
}

function ExportButton({ href, label, accent }: { href?: string; label: string; accent?: boolean }) {
  const base =
    "group inline-flex items-center gap-2 rounded-full border px-5 py-2.5 text-sm font-medium transition duration-200";

  if (!href) {
    return (
      <span
        title="Unavailable"
        aria-disabled="true"
        className={`${base} cursor-not-allowed border-line bg-bone text-muted/50`}
      >
        <Download className="h-4 w-4" aria-hidden />
        {label}
      </span>
    );
  }

  return (
    <a
      href={href}
      download
      target="_blank"
      rel="noreferrer"
      className={`${base} hover:-translate-y-0.5 hover:shadow-md ${
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
