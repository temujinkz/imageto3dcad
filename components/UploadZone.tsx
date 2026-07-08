"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { ImagePlus, Loader2, Plus, X } from "lucide-react";
import { ACCEPT_ATTRIBUTE, isSupportedMedia, isVideoFile, normalizeMediaFiles } from "@/lib/imageConvert";
import { DepthButton } from "@/components/ui/DepthButton";

type UploadZoneProps = {
  previewUrls: string[];
  isVideo: boolean;
  busy: boolean;
  busyLabel?: string;
  error?: string | null;
  onFilesReady: (files: File[], video: File | null) => void;
  onGenerate: () => void;
  onReset: () => void;
};

export function UploadZone({
  previewUrls,
  isVideo,
  busy,
  busyLabel,
  error,
  onFilesReady,
  onGenerate,
  onReset
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const hasMedia = previewUrls.length > 0;

  async function handleFiles(fileList: File[]) {
    const candidates = fileList.filter(isSupportedMedia);
    if (!candidates.length) {
      setLocalError("Add photos (PNG, JPG, HEIC, WebP) or a short orbit video.");
      return;
    }
    setLocalError(null);
    const video = candidates.find(isVideoFile) ?? null;
    const images = candidates.filter((candidate) => !isVideoFile(candidate));
    try {
      if (video) {
        onFilesReady([], video);
        return;
      }
      const normalized = await normalizeMediaFiles(images);
      onFilesReady(normalized, null);
    } catch (conversionError) {
      setLocalError(conversionError instanceof Error ? conversionError.message : "Could not read that file.");
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (files.length) void handleFiles(files);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    if (busy) return;
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length) void handleFiles(files);
  }

  const openPicker = () => !busy && inputRef.current?.click();

  return (
    <section className="rounded-card border border-line bg-card p-4 shadow-card sm:p-5">
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        multiple
        accept={ACCEPT_ATTRIBUTE}
        onChange={handleInputChange}
        disabled={busy}
      />

      {!hasMedia ? (
        <div
          onDragEnter={(event) => {
            event.preventDefault();
            if (!busy) setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
          onClick={openPicker}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && openPicker()}
          className={`flex min-h-[300px] cursor-pointer flex-col items-center justify-center rounded-[14px] border border-dashed px-6 text-center transition ${
            dragActive ? "border-accent bg-accent/5" : "border-line bg-bone/60 hover:border-accent/60 hover:bg-bone"
          }`}
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <ImagePlus className="h-7 w-7" aria-hidden />
          </div>
          <p className="text-lg font-semibold tracking-tight text-ink">Drop photos of your object</p>
          <p className="mt-1.5 max-w-sm text-sm leading-6 text-muted">
            Front, side, any angles you have. More angles give a better model. Or drop a short orbit video.
          </p>
          <span className="mt-5 inline-flex items-center gap-2 rounded-full border border-line bg-card px-4 py-2 text-sm font-medium text-ink">
            <Plus className="h-4 w-4" aria-hidden /> Choose files
          </span>
        </div>
      ) : (
        <div>
          {isVideo ? (
            <div className="overflow-hidden rounded-[14px] border border-line bg-black">
              <video src={previewUrls[0]} controls className="max-h-[320px] w-full" />
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-5">
              {previewUrls.slice(0, 10).map((url, index) => (
                <div
                  key={url}
                  className="relative aspect-square overflow-hidden rounded-xl border border-line bg-bone"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={url} alt={`Angle ${index + 1}`} className="h-full w-full object-cover" />
                </div>
              ))}
              {!busy && (
                <button
                  type="button"
                  onClick={openPicker}
                  className="flex aspect-square flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-line bg-bone/60 text-muted transition hover:border-accent/60 hover:text-accent"
                >
                  <Plus className="h-5 w-5" aria-hidden />
                  <span className="text-xs font-medium">Add</span>
                </button>
              )}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onReset}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card px-3.5 py-2 text-sm font-medium text-muted transition hover:text-ink disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" aria-hidden /> Clear
              </button>
              <span className="text-sm text-muted">
                {isVideo ? "Video ready" : `${previewUrls.length} photo${previewUrls.length > 1 ? "s" : ""}`}
              </span>
            </div>

            <DepthButton onClick={onGenerate} disabled={busy}>
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  {busyLabel ?? "Generating"}
                </>
              ) : (
                "Generate 3D model"
              )}
            </DepthButton>
          </div>
        </div>
      )}

      {(localError || error) && <p className="mt-3 text-sm font-medium text-accent">{localError ?? error}</p>}
    </section>
  );
}
