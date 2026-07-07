import type { JobResponse, ProcessResponse, UploadResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
    throw new Error(body || `Request failed with status ${response.status}`);
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
