const IMAGE_EXTENSIONS = new Set([
  "png",
  "jpg",
  "jpeg",
  "webp",
  "bmp",
  "tif",
  "tiff",
  "gif",
  "heic",
  "heif",
  "avif"
]);

const VIDEO_EXTENSIONS = new Set(["mp4", "mov", "webm", "m4v", "avi", "mkv"]);

const HEIC_EXTENSIONS = new Set(["heic", "heif"]);

export function isImageFile(file: File) {
  const extension = extensionOf(file);
  if (IMAGE_EXTENSIONS.has(extension)) {
    return true;
  }
  return file.type.startsWith("image/");
}

export function isVideoFile(file: File) {
  const extension = extensionOf(file);
  if (VIDEO_EXTENSIONS.has(extension)) {
    return true;
  }
  return file.type.startsWith("video/");
}

export function isSupportedMedia(file: File) {
  return isImageFile(file) || isVideoFile(file);
}

export function extensionOf(file: File) {
  const parts = file.name.toLowerCase().split(".");
  return parts.length > 1 ? parts.pop() ?? "" : "";
}

export async function normalizeToPng(file: File): Promise<File> {
  const extension = extensionOf(file);

  if (extension === "png" && file.type === "image/png") {
    return file;
  }

  if (HEIC_EXTENSIONS.has(extension)) {
    const heic2any = (await import("heic2any")).default;
    const converted = await heic2any({ blob: file, toType: "image/png" });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return new File([blob], replaceExtension(file.name, "png"), { type: "image/png" });
  }

  if (file.type.startsWith("image/") || IMAGE_EXTENSIONS.has(extension)) {
    const bitmap = await createImageBitmap(file);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Could not prepare image canvas.");
    }
    context.drawImage(bitmap, 0, 0);
    bitmap.close();
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("PNG conversion failed."))), "image/png");
    });
    return new File([blob], replaceExtension(file.name, "png"), { type: "image/png" });
  }

  return file;
}

async function decodeToBitmap(file: File): Promise<ImageBitmap> {
  const extension = extensionOf(file);
  if (HEIC_EXTENSIONS.has(extension) || file.type === "image/heic" || file.type === "image/heif") {
    const heic2any = (await import("heic2any")).default;
    const converted = await heic2any({ blob: file, toType: "image/png" });
    const blob = Array.isArray(converted) ? converted[0] : converted;
    return createImageBitmap(blob);
  }
  return createImageBitmap(file);
}

// Builds a small, guaranteed-renderable JPEG data URL for the upload preview.
// Uses a data URL (not a blob: URL) so there is no object-URL lifecycle to
// mismanage, and decodes HEIC first so iPhone photos never render as a blank
// white square in an <img> tag. Returns null if the file cannot be decoded at
// all (the UI then shows a labeled placeholder instead of a broken image).
export async function createPreviewThumbnail(file: File, maxSize = 512): Promise<string | null> {
  try {
    const bitmap = await decodeToBitmap(file);
    const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height, 1));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      bitmap.close();
      return null;
    }
    context.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();
    return canvas.toDataURL("image/jpeg", 0.82);
  } catch {
    return null;
  }
}

export async function createPreviewThumbnails(files: File[]): Promise<(string | null)[]> {
  return Promise.all(files.map((file) => createPreviewThumbnail(file)));
}

export async function normalizeMediaFiles(files: File[]): Promise<File[]> {
  const normalized: File[] = [];
  for (const file of files) {
    if (isVideoFile(file)) {
      normalized.push(file);
      continue;
    }
    try {
      normalized.push(await normalizeToPng(file));
    } catch {
      // Client-side HEIC/canvas conversion (heic2any, createImageBitmap) can
      // fail on real-world files in ways that aren't worth blocking the
      // upload over - the backend converts formats itself and is more
      // robust, so just hand it the original file instead.
      normalized.push(file);
    }
  }
  return normalized;
}

function replaceExtension(name: string, nextExtension: string) {
  const base = name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name;
  return `${base}.${nextExtension}`;
}

export const ACCEPT_ATTRIBUTE =
  "image/*,video/*,.heic,.heif,.avif,.webp,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.gif,.mp4,.mov,.webm,.m4v,.avi,.mkv";
