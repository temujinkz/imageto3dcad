"use client";

import { Boxes, Eraser, Sparkles, Wrench } from "lucide-react";
import type { Capabilities } from "@/lib/api";

function activeReconstructionBackend(capabilities: Capabilities | null): string | null {
  if (!capabilities) return null;
  if (capabilities.meshy_configured) return "Meshy.ai";
  if (capabilities.csm_configured) return "CSM.ai";
  if (capabilities.luma_configured) return "Luma Dream Machine";
  if (capabilities.tripo_api_configured) return "Tripo API";
  if (capabilities.triposr_configured) return "self-hosted TripoSR";
  return null;
}

export function InfoPanel({ capabilities }: { capabilities?: Capabilities | null }) {
  const backend = activeReconstructionBackend(capabilities ?? null);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-soft">
      <div className="mb-5">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">About Photo2CAD</p>
        <h2 className="text-2xl font-semibold text-ink">From a photo to a CAD-ready file, automatically</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Drop a photo, a set of angle photos, or a short orbit video. Photo2CAD strips the background, reconstructs a
          3D mesh, estimates real-world dimensions, and prepares STEP/OBJ files you can open directly in FreeCAD.
        </p>
        {capabilities && (
          <p className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            <span className={`h-1.5 w-1.5 rounded-full ${backend ? "bg-emerald-500" : "bg-amber-500"}`} />
            {backend
              ? `Multi-view 3D reconstruction active: ${backend}`
              : "No 3D reconstruction API configured — add an API key to .env.local for full-fidelity models"}
          </p>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <InfoItem
          icon={<Eraser className="h-5 w-5" aria-hidden />}
          title="Background removal"
          body="Every upload is automatically cut out from its background before reconstruction, so a plain backdrop isn't required."
        />
        <InfoItem
          icon={<Boxes className="h-5 w-5" aria-hidden />}
          title="Multi-angle & video"
          body="A single photo gives a quick estimate. Multiple angle photos or a slow orbit video feed a cloud 3D reconstruction API for higher fidelity."
        />
        <InfoItem
          icon={<Sparkles className="h-5 w-5" aria-hidden />}
          title="Any format, handled"
          body="PNG, JPG, HEIC/HEIF from iPhone, WebP, and common video formats are converted automatically. You never have to think about file type."
        />
        <InfoItem
          icon={<Wrench className="h-5 w-5" aria-hidden />}
          title="FreeCAD-ready"
          body="Results are exported as STEP and OBJ, prepared to open directly in FreeCAD for further editing."
        />
      </div>

      <div className="mt-6 rounded-md border border-blue-100 bg-blue-50 px-4 py-4">
        <h3 className="text-sm font-semibold text-blue-900">Tips for the best results</h3>
        <ul className="mt-2 grid gap-1.5 text-sm leading-6 text-blue-900 sm:grid-cols-2">
          <li>&bull; Fill the frame with the object</li>
          <li>&bull; Use even, diffuse lighting (avoid harsh shadows)</li>
          <li>&bull; Prefer a matte, non-reflective, non-transparent object</li>
          <li>&bull; For best fidelity, capture 8-12 angles or a slow 360&deg; video</li>
          <li>&bull; A plain, uncluttered background helps but isn&apos;t required</li>
          <li>&bull; Add a known width or height for accurate real-world scale</li>
        </ul>
      </div>

      <p className="mt-5 text-sm leading-6 text-slate-600">
        Output is an estimated CAD starting point for engineering workflows, not an exact manufacturing-grade model.
      </p>
    </section>
  );
}

function InfoItem({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3 inline-flex rounded-md bg-white p-2 text-blue-600 shadow-sm">{icon}</div>
      <h3 className="font-semibold text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}
