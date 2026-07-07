"use client";

import { useState } from "react";
import { ChevronDown, Settings2 } from "lucide-react";

export type Dimensions = {
  known_width_mm: string;
  known_height_mm: string;
  thickness_mm: string;
};

type AdvancedOptionsProps = {
  dimensions: Dimensions;
  disabled: boolean;
  onChange: (key: keyof Dimensions, value: string) => void;
};

export function AdvancedOptions({ dimensions, disabled, onChange }: AdvancedOptionsProps) {
  const [open, setOpen] = useState(false);

  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
          <Settings2 className="h-4 w-4 text-blue-600" aria-hidden />
          Advanced: known dimensions (optional)
        </span>
        <ChevronDown className={`h-4 w-4 text-slate-500 transition ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {open && (
        <div className="border-t border-slate-100 px-5 py-4">
          <p className="mb-3 text-sm text-slate-600">
            Photo2CAD estimates real-world scale automatically. Enter a known measurement for a more accurate result.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <DimensionInput
              label="Known width"
              value={dimensions.known_width_mm}
              disabled={disabled}
              onChange={(value) => onChange("known_width_mm", value)}
            />
            <DimensionInput
              label="Known height"
              value={dimensions.known_height_mm}
              disabled={disabled}
              onChange={(value) => onChange("known_height_mm", value)}
            />
            <DimensionInput
              label="Thickness"
              placeholder="5"
              value={dimensions.thickness_mm}
              disabled={disabled}
              onChange={(value) => onChange("thickness_mm", value)}
            />
          </div>
        </div>
      )}
    </section>
  );
}

function DimensionInput({
  label,
  value,
  placeholder,
  disabled,
  onChange
}: {
  label: string;
  value: string;
  placeholder?: string;
  disabled: boolean;
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
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50"
      />
    </label>
  );
}
