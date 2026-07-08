"use client";

import { useEffect, useRef, useState } from "react";
import { DownloadPanel } from "@/components/DownloadPanel";
import { ModelViewer } from "@/components/ModelViewer";
import { UploadZone } from "@/components/UploadZone";
import { CADIntelligenceLogo } from "@/components/CADIntelligenceLogo";
import { Typer } from "@/components/ui/Typer";
import { processJob, uploadMedia } from "@/lib/api";
import { createPreviewThumbnails } from "@/lib/imageConvert";
import type { PipelineResult } from "@/lib/types";

const failureMessage = "Generation failed. Try clearer photos of a simple object, ideally a few angles.";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [video, setVideo] = useState<File | null>(null);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [isVideo, setIsVideo] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Generating");
  const [error, setError] = useState<string | null>(null);
  // Only video previews use a revocable object URL; image previews are data
  // URLs (see createPreviewThumbnails) so there is no lifecycle to manage.
  const videoUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (videoUrlRef.current) URL.revokeObjectURL(videoUrlRef.current);
    };
  }, []);

  function revokeVideoUrl() {
    if (videoUrlRef.current) {
      URL.revokeObjectURL(videoUrlRef.current);
      videoUrlRef.current = null;
    }
  }

  async function handleFilesReady(nextFiles: File[], nextVideo: File | null) {
    revokeVideoUrl();
    setResult(null);
    setError(null);
    if (nextVideo) {
      const url = URL.createObjectURL(nextVideo);
      videoUrlRef.current = url;
      setVideo(nextVideo);
      setFiles([]);
      setIsVideo(true);
      setPreviewUrls([url]);
    } else {
      setVideo(null);
      setFiles(nextFiles);
      setIsVideo(false);
      // Show something immediately, then swap in decoded thumbnails so HEIC and
      // other formats render instead of appearing as blank white squares.
      setPreviewUrls(nextFiles.map(() => ""));
      const thumbs = await createPreviewThumbnails(nextFiles);
      setPreviewUrls(thumbs.map((thumb) => thumb ?? ""));
    }
  }

  function handleReset() {
    revokeVideoUrl();
    setFiles([]);
    setVideo(null);
    setPreviewUrls([]);
    setIsVideo(false);
    setResult(null);
    setError(null);
  }

  async function handleGenerate() {
    if (busy || (files.length === 0 && !video)) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setBusyLabel("Uploading");
      const uploadResponse = await uploadMedia(files, video);
      setBusyLabel("Working on it");
      const processResponse = await processJob(uploadResponse.job_id);
      setResult({
        previewModelUrl: processResponse.preview_model_url,
        fullModelUrl: processResponse.full_model_url,
        files: processResponse.files,
        freecad: processResponse.freecad,
        cadSummary: processResponse.cad_summary,
        warnings: processResponse.warnings,
        meshSource: processResponse.mesh_source,
        meshIsHighFidelity: processResponse.mesh_is_high_fidelity
      });
    } catch (pipelineError) {
      setError(pipelineError instanceof Error ? pipelineError.message : failureMessage);
    } finally {
      setBusy(false);
    }
  }

  const showViewer = busy || Boolean(result?.previewModelUrl);

  return (
    <main className="min-h-screen bg-bone">
      <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
        <header className="mb-8">
          <div className="mb-4 flex items-center gap-2.5">
            <CADIntelligenceLogo className="h-7 w-7" />
            <span className="text-sm font-semibold uppercase tracking-wide text-muted">CAD Intelligence</span>
          </div>
          <Typer
            text="Turn a photo into a 3D model"
            className="text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem] sm:leading-[1.1]"
          />
        </header>

        <div className="space-y-5">
          <UploadZone
            previewUrls={previewUrls}
            isVideo={isVideo}
            busy={busy}
            busyLabel={busyLabel}
            error={error}
            onFilesReady={handleFilesReady}
            onGenerate={handleGenerate}
            onReset={handleReset}
          />

          {showViewer && (
            <ModelViewer
              modelUrl={result?.previewModelUrl}
              fullModelUrl={result?.fullModelUrl}
              meshIsHighFidelity={result?.meshIsHighFidelity}
              warnings={result?.warnings}
              busy={busy}
              busyLabel={busyLabel}
            />
          )}

          {result && <DownloadPanel result={result} />}
        </div>
      </div>
    </main>
  );
}
