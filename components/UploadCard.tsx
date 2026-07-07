"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { ImagePlus, UploadCloud } from "lucide-react";

type UploadCardProps = {
  file: File | null;
  imagePreviewUrl: string | null;
  backendImageUrl?: string;
  maskedImageUrl?: string;
  jobId?: string;
  isUploading: boolean;
  isProcessing: boolean;
  onFileSelect: (file: File) => void;
  onUpload: () => void;
};

const acceptedTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp"];

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function UploadCard({
  file,
  imagePreviewUrl,
  backendImageUrl,
  maskedImageUrl,
  jobId,
  isUploading,
  isProcessing,
  onFileSelect,
  onUpload
}: UploadCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function handleFile(nextFile: File) {
    if (!acceptedTypes.includes(nextFile.type)) {
      setLocalError("Use a PNG, JPG, JPEG, or WebP image.");
      return;
    }

    setLocalError(null);
    onFileSelect(nextFile);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0];
    if (nextFile) {
      handleFile(nextFile);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);

    const nextFile = event.dataTransfer.files?.[0];
    if (nextFile) {
      handleFile(nextFile);
    }
  }

  return (
    <section id="upload" className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Step 1</p>
          <h2 className="text-2xl font-semibold text-ink">Upload object photo</h2>
        </div>
        <ImagePlus className="h-6 w-6 text-blue-600" aria-hidden />
      </div>

      <div
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        className={`flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-5 text-center transition ${
          dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50"
        }`}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          className="hidden"
          type="file"
          accept="image/png,image/jpeg,image/jpg,image/webp"
          onChange={handleInputChange}
        />

        {imagePreviewUrl ? (
          <div className="w-full">
            <div className="checkerboard mx-auto mb-4 flex max-h-[360px] max-w-full items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={imagePreviewUrl} alt="Uploaded object preview" className="max-h-[360px] w-full object-contain" />
            </div>
            {file && (
              <div className="flex flex-wrap items-center justify-center gap-2 text-sm text-slate-600">
                <span className="font-medium text-ink">{file.name}</span>
                <span>{formatBytes(file.size)}</span>
              </div>
            )}
          </div>
        ) : (
          <>
            <UploadCloud className="mb-3 h-10 w-10 text-blue-600" aria-hidden />
            <p className="text-lg font-semibold text-ink">Drag and drop an object photo</p>
            <p className="mt-1 text-sm text-slate-600">PNG, JPG, JPEG, or WebP. Top-down photos of simple parts work best.</p>
          </>
        )}
      </div>

      {localError && <p className="mt-3 text-sm font-medium text-red-600">{localError}</p>}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onUpload}
          disabled={!file || isUploading || isProcessing}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <UploadCloud className="h-4 w-4" aria-hidden />
          {isUploading ? "Uploading..." : "Upload to Backend"}
        </button>
        {jobId && <span className="text-xs text-slate-500">Job ID: {jobId}</span>}
      </div>

      {(backendImageUrl || maskedImageUrl) && (
        <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
          {backendImageUrl && <PreviewLink label="Uploaded image URL" url={backendImageUrl} />}
          {maskedImageUrl && <PreviewLink label="Masked image URL" url={maskedImageUrl} />}
        </div>
      )}
    </section>
  );
}

function PreviewLink({ label, url }: { label: string; url: string }) {
  return (
    <a href={url} target="_blank" rel="noreferrer" className="truncate rounded-md border border-slate-200 bg-slate-50 px-3 py-2 hover:border-blue-300">
      <span className="mr-2 font-medium text-ink">{label}:</span>
      <span>{url}</span>
    </a>
  );
}
