"use client";

import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import type { JobResponse } from "@/lib/types";

type ProgressPanelProps = {
  step: string;
  job?: JobResponse | null;
  isProcessing: boolean;
  error?: string | null;
};

export function ProgressPanel({ step, job, isProcessing, error }: ProgressPanelProps) {
  const progress = Math.max(0, Math.min(100, job?.progress ?? (isProcessing ? 18 : 0)));
  const completed = job?.status === "completed" || step === "Completed";
  const failed = Boolean(error) || job?.status === "failed";

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Progress</p>
          <h2 className="text-2xl font-semibold text-ink">{step}</h2>
        </div>
        {failed ? (
          <TriangleAlert className="h-6 w-6 text-red-500" aria-hidden />
        ) : completed ? (
          <CheckCircle2 className="h-6 w-6 text-emerald-600" aria-hidden />
        ) : (
          <Loader2 className={`h-6 w-6 text-blue-600 ${isProcessing ? "animate-spin" : ""}`} aria-hidden />
        )}
      </div>

      <div className="h-3 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${failed ? "bg-red-500" : completed ? "bg-emerald-500" : "bg-blue-600"}`}
          style={{ width: `${failed ? 100 : progress}%` }}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
        <span>{error ?? job?.message ?? "Ready when the backend is connected."}</span>
        <span className="font-medium text-ink">{failed ? "Failed" : `${Math.round(failed ? 100 : progress)}%`}</span>
      </div>
    </section>
  );
}
