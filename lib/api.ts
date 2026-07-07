import type { JobResponse, ProcessResponse, UploadResponse } from "@/lib/types";

// Defaults to a relative/same-origin base so the unified single-port build
// (frontend served by the FastAPI backend, see app/main.py) works regardless
// of which port that backend actually binds to. Override with
// NEXT_PUBLIC_API_BASE_URL for the two-process hot-reload dev workflow
// (npm run dev on :3000 talking to a backend on a different port).
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function extractErrorMessage(body: string): string {
  if (!body) return "";
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg ?? JSON.stringify(item)).join("; ");
    }
    return body;
  } catch {
    return body;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers
    }
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(extractErrorMessage(body) || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type Capabilities = {
  rembg_available: boolean;
  triposr_enabled: boolean;
  triposr_configured: boolean;
  luma_configured: boolean;
  csm_configured: boolean;
  tripo_api_configured: boolean;
  meshy_configured: boolean;
  supported_image_formats: string[];
  supported_video_formats: string[];
};

export async function getCapabilities() {
  return requestJson<Capabilities>("/api/capabilities");
}

export async function uploadMedia(files: File[], video?: File | null): Promise<UploadResponse> {
  const formData = new FormData();

  if (video) {
    formData.append("video", video);
  } else if (files.length === 1) {
    formData.append("image", files[0]);
  } else {
    files.forEach((file) => formData.append("images", file));
  }

  formData.append("background_removal", "true");

  return requestJson<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData
  });
}

export type ProcessOptions = {
  known_width_mm?: number;
  known_height_mm?: number;
  thickness_mm?: number;
};

export async function processJob(jobId: string, options: ProcessOptions = {}): Promise<ProcessResponse> {
  return requestJson<ProcessResponse>("/api/process", {
    method: "POST",
    body: JSON.stringify({
      job_id: jobId,
      generate_mesh: true,
      generate_cad: true,
      generate_freecad: true,
      ...options
    })
  });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/api/jobs/${jobId}`);
}

export { API_BASE_URL };
