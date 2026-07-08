"use client";

import { useEffect, useRef, useState } from "react";
import { Boxes } from "lucide-react";
import { DownloadPanel } from "@/components/DownloadPanel";
import { ModelViewer } from "@/components/ModelViewer";
import { UploadZone } from "@/components/UploadZone";
import { processJob, uploadMedia } from "@/lib/api";
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
  const previewUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    previewUrlsRef.current = previewUrls;
  }, [previewUrls]);

  useEffect(() => {
    return () => previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  function revokePreviews() {
    previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
  }

  function handleFilesReady(nextFiles: File[], nextVideo: File | null) {
    revokePreviews();
    setResult(null);
    setError(null);
    if (nextVideo) {
      setVideo(nextVideo);
      setFiles([]);
      setIsVideo(true);
      setPreviewUrls([URL.createObjectURL(nextVideo)]);
    } else {
      setVideo(null);
      setFiles(nextFiles);
      setIsVideo(false);
      setPreviewUrls(nextFiles.map((file) => URL.createObjectURL(file)));
    }
  }

  function handleReset() {
    revokePreviews();
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
      setBusyLabel("Generating 3D model");
      const processResponse = await processJob(uploadResponse.job_id);
      setResult({
        previewModelUrl: processResponse.preview_model_url,
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
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 text-xs font-medium text-muted">
            <Boxes className="h-3.5 w-3.5 text-accent" aria-hidden />
            image to 3D CAD
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-[2.5rem] sm:leading-[1.1]">
            Photos in. 3D model out.
          </h1>
          <p className="mt-2 max-w-xl text-base leading-7 text-muted">
            Drop a few angles of an object, generate a 3D model you can spin, then download it as a mesh or a
            CAD file for AutoCAD and FreeCAD.
          </p>
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
              meshSource={result?.meshSource}
              meshIsHighFidelity={result?.meshIsHighFidelity}
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
