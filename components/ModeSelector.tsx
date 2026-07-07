"use client";

import { Box, DraftingCompass, Loader2 } from "lucide-react";

type ModeSelectorProps = {
  canGenerate: boolean;
  isProcessing: boolean;
  cadDimensions: {
    known_width_mm: string;
    known_height_mm: string;
    thickness_mm: string;
  };
  showScaleWarning: boolean;
  onCadDimensionChange: (key: "known_width_mm" | "known_height_mm" | "thickness_mm", value: string) => void;
  onGenerateMesh: () => void;
  onGenerateCad: () => void;
};

export function ModeSelector({
  canGenerate,
  isProcessing,
  cadDimensions,
  showScaleWarning,
  onCadDimensionChange,
  onGenerateMesh,
  onGenerateCad
}: ModeSelectorProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <ModeCard
        icon={<Box className="h-6 w-6 text-blue-600" aria-hidden />}
        title="Mesh Mode"
        description="Fast visual 3D reconstruction. Best for preview, STL, OBJ, GLB."
      >
        <button
          type="button"
          onClick={onGenerateMesh}
          disabled={!canGenerate || isProcessing}
          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Box className="h-4 w-4" aria-hidden />}
          Generate 3D Mesh
        </button>
      </ModeCard>

      <ModeCard
        icon={<DraftingCompass className="h-6 w-6 text-blue-600" aria-hidden />}
        title="CAD Draft Mode"
        description="Best for simple flat parts. Detects outline/holes and exports STEP/DXF."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <DimensionInput
            label="Known width"
            value={cadDimensions.known_width_mm}
            onChange={(value) => onCadDimensionChange("known_width_mm", value)}
          />
          <DimensionInput
            label="Known height"
            value={cadDimensions.known_height_mm}
            onChange={(value) => onCadDimensionChange("known_height_mm", value)}
          />
          <DimensionInput
            label="Thickness"
            placeholder="5"
            value={cadDimensions.thickness_mm}
            onChange={(value) => onCadDimensionChange("thickness_mm", value)}
          />
        </div>
        {showScaleWarning && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Without a known dimension, CAD scale will be estimated.
          </p>
        )}
        <button
          type="button"
          onClick={onGenerateCad}
          disabled={!canGenerate || isProcessing}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <DraftingCompass className="h-4 w-4" aria-hidden />}
          Generate CAD Draft
        </button>
      </ModeCard>
    </section>
  );
}

function ModeCard({
  icon,
  title,
  description,
  children
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-start gap-3">
        <div className="rounded-md bg-blue-50 p-2">{icon}</div>
        <div>
          <h2 className="text-xl font-semibold text-ink">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function DimensionInput({
  label,
  value,
  placeholder,
  onChange
}: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">{label} in mm</span>
      <input
        type="number"
        min="0"
        step="0.1"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      />
    </label>
  );
}
