"use client";

import { useEffect, useRef, useState } from "react";
import { AdvancedOptions, type Dimensions } from "@/components/AdvancedOptions";
import { DownloadPanel } from "@/components/DownloadPanel";
import { InfoPanel } from "@/components/InfoPanel";
import { ModelViewer } from "@/components/ModelViewer";
import { ProgressPanel } from "@/components/ProgressPanel";
import { UploadCard } from "@/components/UploadCard";
import { getCapabilities, processJob, uploadMedia, type Capabilities, type ProcessOptions } from "@/lib/api";
import type { JobResponse, PipelineResult, UploadResponse, WorkflowStep } from "@/lib/types";

const failureMessage = "Generation failed. Try a clearer photo of a simple object, ideally with a few extra angles.";

export default function Home() {
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isVideoPreview, setIsVideoPreview] = useState(false);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [step, setStep] = useState<WorkflowStep>("Ready");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [dimensions, setDimensions] = useState<Dimensions>({
    known_width_mm: "",
    known_height_mm: "",
    thickness_mm: ""
  });
  const previewUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    getCapabilities()
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
  }, []);

  useEffect(() => {
    previewUrlsRef.current = previewUrls;
  }, [previewUrls]);

  useEffect(() => {
    return () => {
      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  function resetPreviews() {
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    setPreviewUrls([]);
    setIsVideoPreview(false);
  }

  function handleReset() {
    resetPreviews();
    setUpload(null);
    setJob(null);
    setResult(null);
    setError(null);
    setStep("Ready");
  }

  async function handleMediaReady(files: File[], video: File | null) {
    resetPreviews();
    setUpload(null);
    setJob(null);
    setResult(null);
    setError(null);

    if (video) {
      setIsVideoPreview(true);
      setPreviewUrls([URL.createObjectURL(video)]);
    } else {
      setPreviewUrls(files.map((file) => URL.createObjectURL(file)));
    }

    await runPipeline(files, video);
  }

  async function runPipeline(files: File[], video: File | null) {
    setBusy(true);
    setStep("Converting format");

    try {
      setStep("Uploading");
      const uploadResponse = await uploadMedia(files, video);
      setUpload(uploadResponse);

      setStep("Removing background");
      setStep("Generating 3D model");
      const processResponse = await processJob(uploadResponse.job_id, buildDimensionOptions(dimensions));

      setStep("Preparing CAD exports");
      setResult({
        previewModelUrl: processResponse.preview_model_url,
        files: processResponse.files,
        freecad: processResponse.freecad,
        cadSummary: processResponse.cad_summary,
        warnings: processResponse.warnings,
        meshSource: processResponse.mesh_source,
        meshIsHighFidelity: processResponse.mesh_is_high_fidelity
      });
      setJob({
        job_id: processResponse.job_id,
        status: processResponse.status,
        progress: 100,
        message: processResponse.message,
        preview_model_url: processResponse.preview_model_url,
        files: processResponse.files,
        freecad: processResponse.freecad,
        warnings: processResponse.warnings,
        mesh_source: processResponse.mesh_source,
        mesh_is_high_fidelity: processResponse.mesh_is_high_fidelity
      });
      setStep("Completed");
    } catch (pipelineError) {
      setError(pipelineError instanceof Error ? pipelineError.message : failureMessage);
      setStep("Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl flex-col gap-1 px-4 py-6 sm:px-6">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
            Photo2CAD
          </span>
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Drop a photo. Get a 3D CAD file.</h1>
          <p className="max-w-2xl text-base text-slate-600">
            Background removal, 3D reconstruction, and FreeCAD-ready exports happen automatically.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
        <UploadCard
          busy={busy}
          busyLabel={step}
          disabled={busy}
          error={error}
          previewUrls={previewUrls}
          isVideoPreview={isVideoPreview}
          onMediaReady={handleMediaReady}
          onReset={handleReset}
        />

        {(busy || job) && <ProgressPanel step={step} job={job} isProcessing={busy} error={error} />}

        {result?.previewModelUrl && (
          <ModelViewer
            modelUrl={result.previewModelUrl}
            mode="both"
            meshSource={result.meshSource}
            meshIsHighFidelity={result.meshIsHighFidelity}
          />
        )}

        {result && <DownloadPanel result={result} />}

        <AdvancedOptions
          dimensions={dimensions}
          disabled={busy}
          onChange={(key, value) => setDimensions((current) => ({ ...current, [key]: value }))}
        />

        <InfoPanel capabilities={capabilities} />
      </div>
    </main>
  );
}

function buildDimensionOptions(dimensions: Dimensions): ProcessOptions {
  const options: ProcessOptions = {};
  const width = parseOptionalNumber(dimensions.known_width_mm);
  const height = parseOptionalNumber(dimensions.known_height_mm);
  const thickness = parseOptionalNumber(dimensions.thickness_mm);
  if (width !== undefined) options.known_width_mm = width;
  if (height !== undefined) options.known_height_mm = height;
  if (thickness !== undefined) options.thickness_mm = thickness;
  return options;
}

function parseOptionalNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}
