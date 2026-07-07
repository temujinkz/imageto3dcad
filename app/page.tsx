"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, ImagePlus } from "lucide-react";
import { DownloadPanel } from "@/components/DownloadPanel";
import { InfoPanel } from "@/components/InfoPanel";
import { ModeSelector } from "@/components/ModeSelector";
import { ModelViewer } from "@/components/ModelViewer";
import { ProgressPanel } from "@/components/ProgressPanel";
import { UploadCard } from "@/components/UploadCard";
import { generateCad, generateMesh, getJob, uploadImage } from "@/lib/api";
import type { GeneratedResult, GenerationMode, JobResponse, UploadResponse } from "@/lib/types";

const failureMessage = "Generation failed. Try a clearer image with a simple object on a plain background.";

type WorkflowStep =
  | "Ready"
  | "Uploading image"
  | "Removing background"
  | "Generating mesh"
  | "Reconstructing CAD"
  | "Exporting files"
  | "Completed";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [result, setResult] = useState<GeneratedResult | null>(null);
  const [step, setStep] = useState<WorkflowStep>("Ready");
  const [activeMode, setActiveMode] = useState<GenerationMode | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cadDimensions, setCadDimensions] = useState({
    known_width_mm: "",
    known_height_mm: "",
    thickness_mm: ""
  });

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!upload?.job_id || !isProcessing) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const nextJob = await getJob(upload.job_id);
        setJob(nextJob);

        if (nextJob.status === "failed") {
          setError(failureMessage);
          setIsProcessing(false);
          setStep("Ready");
        }

        if (nextJob.status === "completed") {
          setStep("Exporting files");
        }
      } catch {
        // Generation calls still resolve with final assets, so polling failure should not hide that result.
      }
    }, 1400);

    return () => window.clearInterval(interval);
  }, [upload?.job_id, isProcessing]);

  const showScaleWarning = useMemo(
    () => !cadDimensions.known_width_mm && !cadDimensions.known_height_mm,
    [cadDimensions.known_height_mm, cadDimensions.known_width_mm]
  );

  function handleFileSelect(nextFile: File) {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
    setUpload(null);
    setJob(null);
    setResult(null);
    setError(null);
    setStep("Ready");
  }

  async function handleUpload() {
    if (!file) {
      return;
    }

    setIsUploading(true);
    setError(null);
    setStep("Uploading image");
    setResult(null);

    try {
      const response = await uploadImage(file);
      setUpload(response);
      setJob({
        job_id: response.job_id,
        status: "queued",
        progress: 20,
        message: "Image uploaded. Waiting for generation."
      });
      setStep("Removing background");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed. Check that the backend is running.");
      setStep("Ready");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleGenerateMesh() {
    if (!upload?.job_id) {
      setError("Upload an image to the backend before generation.");
      return;
    }

    setActiveMode("mesh");
    setIsProcessing(true);
    setError(null);
    setStep("Generating mesh");

    try {
      const response = await generateMesh(upload.job_id);
      setResult({
        mode: "mesh",
        previewModelUrl: response.preview_model_url ?? response.files.glb ?? response.files.obj ?? response.files.stl,
        files: response.files
      });
      setJob({
        job_id: response.job_id,
        status: response.status,
        progress: 100,
        message: "Mesh generation completed."
      });
      setStep("Completed");
    } catch {
      setError(failureMessage);
      setStep("Ready");
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleGenerateCad() {
    if (!upload?.job_id) {
      setError("Upload an image to the backend before generation.");
      return;
    }

    setActiveMode("cad");
    setIsProcessing(true);
    setError(null);
    setStep("Reconstructing CAD");

    const knownWidth = parseOptionalNumber(cadDimensions.known_width_mm);
    const knownHeight = parseOptionalNumber(cadDimensions.known_height_mm);
    const thickness = parseOptionalNumber(cadDimensions.thickness_mm) ?? 5;

    try {
      const response = await generateCad(upload.job_id, {
        mode: "flat_part",
        known_width_mm: knownWidth,
        known_height_mm: knownHeight,
        thickness_mm: thickness
      });
      setResult({
        mode: "cad",
        previewModelUrl: response.preview_model_url ?? response.files.stl,
        files: response.files,
        cadSummary: response.cad_summary
      });
      setJob({
        job_id: response.job_id,
        status: response.status,
        progress: 100,
        message: "CAD draft generation completed."
      });
      setStep("Completed");
    } catch {
      setError(failureMessage);
      setStep("Ready");
    } finally {
      setIsProcessing(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <Hero />

      <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 pb-16 pt-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_430px] lg:px-8">
        <div className="space-y-6">
          <UploadCard
            file={file}
            imagePreviewUrl={previewUrl}
            backendImageUrl={upload?.image_url}
            maskedImageUrl={upload?.masked_image_url}
            jobId={upload?.job_id}
            isUploading={isUploading}
            isProcessing={isProcessing}
            onFileSelect={handleFileSelect}
            onUpload={handleUpload}
          />

          <ModeSelector
            canGenerate={Boolean(upload?.job_id)}
            isProcessing={isProcessing || isUploading}
            cadDimensions={cadDimensions}
            showScaleWarning={showScaleWarning}
            onCadDimensionChange={(key, value) => setCadDimensions((current) => ({ ...current, [key]: value }))}
            onGenerateMesh={handleGenerateMesh}
            onGenerateCad={handleGenerateCad}
          />

          <ModelViewer modelUrl={result?.previewModelUrl} mode={result?.mode ?? activeMode ?? undefined} />
        </div>

        <aside className="space-y-6">
          <ProgressPanel step={step} job={job} isProcessing={isProcessing || isUploading} error={error} />
          <DownloadPanel result={result} />
          <InfoPanel />
        </aside>
      </div>
    </main>
  );
}

function Hero() {
  return (
    <section className="border-b border-slate-200 bg-white">
      <div className="mx-auto grid min-h-[520px] max-w-7xl items-center gap-8 px-4 py-12 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8">
        <div>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-800">
            <DraftBadge />
            Estimated CAD prototype
          </div>
          <h1 className="max-w-3xl text-5xl font-semibold tracking-normal text-ink sm:text-6xl">Photo2CAD</h1>
          <p className="mt-5 max-w-2xl text-2xl font-medium text-blue-700">Take a photo. Get a CAD starting point.</p>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-600">
            Upload an object photo and generate an estimated 3D mesh or CAD-friendly draft for engineering workflows.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#upload"
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
            >
              <ImagePlus className="h-4 w-4" aria-hidden />
              Upload Image
            </a>
            <a
              href="#upload"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-blue-400 hover:text-blue-700"
            >
              <ArrowDownToLine className="h-4 w-4" aria-hidden />
              View workflow
            </a>
          </div>
        </div>

        <div className="relative min-h-[360px] overflow-hidden rounded-lg border border-slate-200 bg-slate-950 shadow-soft">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.16)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.16)_1px,transparent_1px)] bg-[size:32px_32px]" />
          <div className="absolute inset-x-8 top-8 rounded-lg border border-slate-700 bg-slate-900/95 p-4 text-slate-100 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b border-slate-700 pb-3">
              <span className="text-sm font-semibold">CAD draft summary</span>
              <span className="rounded bg-emerald-400/15 px-2 py-1 text-xs font-medium text-emerald-300">completed</span>
            </div>
            <div className="grid gap-3 text-sm">
              <Metric label="Detected outline" value="true" />
              <Metric label="Detected holes" value="4" />
              <Metric label="Estimated size" value="120 x 80 x 5 mm" />
            </div>
          </div>
          <div className="absolute bottom-8 left-8 right-8 rounded-lg border border-slate-700 bg-slate-900/95 p-4">
            <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-800">
              <div className="h-full w-[86%] rounded-full bg-blue-400" />
            </div>
            <div className="flex flex-wrap gap-2">
              {["STL", "GLB", "STEP", "DXF"].map((format) => (
                <span key={format} className="rounded border border-slate-700 px-3 py-1 text-xs font-semibold text-slate-200">
                  {format}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function DraftBadge() {
  return <span className="h-2 w-2 rounded-full bg-blue-600" aria-hidden />;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded border border-slate-800 bg-slate-950 px-3 py-2">
      <span className="text-slate-400">{label}</span>
      <span className="font-mono text-slate-100">{value}</span>
    </div>
  );
}

function parseOptionalNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}
