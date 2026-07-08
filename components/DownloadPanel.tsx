"use client";

import { Download, FileBox, Ruler } from "lucide-react";
import type { PipelineResult } from "@/lib/types";

const MESH_KEYS: Record<string, string> = { glb: "GLB", obj: "OBJ", stl: "STL" };
const CAD_KEYS: Record<string, string> = { step: "STEP", dxf: "DXF", cad_stl: "CAD STL" };

export function DownloadPanel({ result }: { result: PipelineResult | null }) {
  const files = result?.files ?? {};
  const mesh = Object.keys(MESH_KEYS).filter((key) => (files as Record<string, string>)[key]);
  const cad = Object.keys(CAD_KEYS).filter((key) => (files as Record<string, string>)[key]);
  const freecadStep = result?.freecad?.step;
  const freecadObj = result?.freecad?.obj;
  const nothing = mesh.length === 0 && cad.length === 0 && !freecadStep && !freecadObj;

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">Download</h2>

      {nothing ? (
        <p className="rounded-[14px] border border-dashed border-line bg-bone px-4 py-6 text-sm text-muted">
          Once you make a model, your files show up here to download.
        </p>
      ) : (
        <div className="space-y-5">
          {mesh.length > 0 && (
            <Group icon={<FileBox className="h-4 w-4" aria-hidden />} title="3D model" hint="for viewing and 3D printing">
              {mesh.map((key) => (
                <Chip key={key} href={(files as Record<string, string>)[key]} label={MESH_KEYS[key]} />
              ))}
            </Group>
          )}

          {(cad.length > 0 || freecadStep || freecadObj) && (
            <Group icon={<Ruler className="h-4 w-4" aria-hidden />} title="CAD" hint="open these in AutoCAD or FreeCAD">
              {cad.map((key) => (
                <Chip
                  key={key}
                  href={(files as Record<string, string>)[key]}
                  label={CAD_KEYS[key]}
                  accent={key === "step"}
                />
              ))}
              {freecadStep && <Chip href={freecadStep} label="FreeCAD STEP" />}
              {freecadObj && <Chip href={freecadObj} label="FreeCAD OBJ" />}
            </Group>
          )}
        </div>
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

function Group({
  icon,
  title,
  hint,
  children
}: {
  icon: React.ReactNode;
  title: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-ink">
        <span className="text-muted">{icon}</span>
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted">{hint}</span>
      </div>
      <div className="flex flex-wrap gap-2.5">{children}</div>
    </div>
  );
}

function Chip({ href, label, accent }: { href: string; label: string; accent?: boolean }) {
  return (
    <a
      href={href}
      download
      target="_blank"
      rel="noreferrer"
      className={`group inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition duration-200 hover:-translate-y-0.5 hover:shadow-md ${
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
