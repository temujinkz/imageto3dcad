"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { Film, Layers, Loader2, UploadCloud, X } from "lucide-react";
import { ACCEPT_ATTRIBUTE, isSupportedMedia, isVideoFile, normalizeMediaFiles } from "@/lib/imageConvert";

type UploadCardProps = {
  busy: boolean;
  busyLabel?: string;
  disabled?: boolean;
  error?: string | null;
  previewUrls: string[];
  isVideoPreview: boolean;
  maskedImageUrl?: string | null;
  onMediaReady: (files: File[], video: File | null) => void;
  onReset: () => void;
};

export function UploadCard({
  busy,
  busyLabel,
  disabled,
  error,
  previewUrls,
  isVideoPreview,
  maskedImageUrl,
  onMediaReady,
  onReset
}: UploadCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const hasMedia = previewUrls.length > 0;

  async function handleFiles(fileList: File[]) {
    const candidates = fileList.filter(isSupportedMedia);
    if (!candidates.length) {
      setLocalError("Drop a photo (PNG/JPG/HEIC/WebP...), a set of angle photos, or a short video.");
      return;
    }

    setLocalError(null);

    const video = candidates.find(isVideoFile) ?? null;
    const images = candidates.filter((candidate) => !isVideoFile(candidate));

    try {
      if (video) {
        onMediaReady([], video);
        return;
      }
      const normalized = await normalizeMediaFiles(images);
      onMediaReady(normalized, null);
    } catch (conversionError) {
      setLocalError(
        conversionError instanceof Error ? conversionError.message : "Could not read that file. Try another photo."
      );
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (files.length) {
      void handleFiles(files);
    }
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (disabled || busy) {
      return;
    }
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length) {
      void handleFiles(files);
    }
  }

  return (
    <section id="upload" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft sm:p-10">
      <div
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled && !busy) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        onClick={() => !disabled && !busy && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-disabled={disabled || busy}
        className={`relative flex min-h-[380px] flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition ${
          disabled || busy ? "cursor-not-allowed opacity-90" : "cursor-pointer"
        } ${dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50"}`}
      >
        <input
          ref={inputRef}
          className="hidden"
          type="file"
          multiple
          accept={ACCEPT_ATTRIBUTE}
          onChange={handleInputChange}
          disabled={disabled || busy}
        />

        {busy ? (
          <>
            <Loader2 className="mb-4 h-12 w-12 animate-spin text-blue-600" aria-hidden />
            <p className="text-xl font-semibold text-ink">{busyLabel ?? "Processing..."}</p>
            <p className="mt-2 text-sm text-slate-600">This can take a moment for 3D reconstruction and CAD export.</p>
          </>
        ) : hasMedia ? (
          <div className="w-full">
            {isVideoPreview ? (
              <div className="mx-auto mb-4 flex max-h-[320px] max-w-full items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-black">
                <video src={previewUrls[0]} controls className="max-h-[320px] w-full" />
              </div>
            ) : maskedImageUrl ? (
              <div className="mx-auto mb-4 max-w-[260px]">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Background removed
                </p>
                <div className="checkerboard flex aspect-square items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={maskedImageUrl} alt="Background removed preview" className="h-full w-full object-contain" />
                </div>
              </div>
            ) : (
              <div className="mx-auto mb-4 grid max-w-full grid-cols-2 gap-3 sm:grid-cols-4">
                {previewUrls.slice(0, 8).map((url, index) => (
                  <div
                    key={url}
                    className="checkerboard flex aspect-square items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={url} alt={`Uploaded angle ${index + 1}`} className="h-full w-full object-contain" />
                  </div>
                ))}
              </div>
            )}
            <p className="text-sm font-medium text-slate-600">
              {isVideoPreview
                ? "Video ready. Drop a new file to replace it."
                : `${previewUrls.length} photo${previewUrls.length > 1 ? "s" : ""} ready. Drop more angles or a new photo to replace.`}
            </p>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onReset();
              }}
              className="mt-4 inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-red-300 hover:text-red-600"
            >
              <X className="h-4 w-4" aria-hidden />
              Start over
            </button>
          </div>
        ) : (
          <>
            <UploadCloud className="mb-4 h-14 w-14 text-blue-600" aria-hidden />
            <p className="text-2xl font-semibold text-ink">Drag & drop your photo here</p>
            <p className="mt-2 max-w-md text-base text-slate-600">
              or click to browse. PNG, JPG, HEIC, WebP, and more all just work.
            </p>
            <div className="mt-5 flex flex-wrap items-center justify-center gap-4 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Layers className="h-4 w-4" aria-hidden /> Drop several angle photos at once
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Film className="h-4 w-4" aria-hidden /> or a short orbit video
              </span>
            </div>
          </>
        )}
      </div>

      {(localError || error) && (
        <p className="mt-4 text-sm font-medium text-red-600">{localError ?? error}</p>
      )}
    </section>
  );
}
