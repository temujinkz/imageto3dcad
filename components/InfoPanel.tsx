"use client";

import { Boxes, DraftingCompass, ImageIcon } from "lucide-react";

export function InfoPanel() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">How it works</p>
        <h2 className="text-2xl font-semibold text-ink">From photo to editable starting point</h2>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <InfoItem
          icon={<ImageIcon className="h-5 w-5" aria-hidden />}
          title="Photo input"
          body="This prototype works best on top-down photos of flat parts against a plain background."
        />
        <InfoItem
          icon={<Boxes className="h-5 w-5" aria-hidden />}
          title="Mesh mode"
          body="Mesh mode creates a visual 3D asset for preview and common mesh exports."
        />
        <InfoItem
          icon={<DraftingCompass className="h-5 w-5" aria-hidden />}
          title="CAD mode"
          body="CAD mode tries to reconstruct engineering primitives like outlines, holes, and extrusions."
        />
      </div>

      <p className="mt-5 rounded-md border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">
        The output is an estimated CAD starting point for engineering workflows, not an exact manufacturing-grade model.
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
