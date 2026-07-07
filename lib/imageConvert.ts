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

export async function normalizeMediaFiles(files: File[]): Promise<File[]> {
  const normalized: File[] = [];
  for (const file of files) {
    if (isVideoFile(file)) {
      normalized.push(file);
      continue;
    }
    normalized.push(await normalizeToPng(file));
  }
  return normalized;
}

function replaceExtension(name: string, nextExtension: string) {
  const base = name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name;
  return `${base}.${nextExtension}`;
}

export const ACCEPT_ATTRIBUTE =
  "image/*,video/*,.heic,.heif,.avif,.webp,.png,.jpg,.jpeg,.bmp,.tif,.tiff,.gif,.mp4,.mov,.webm,.m4v,.avi,.mkv";
