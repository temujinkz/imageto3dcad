import type {
  GenerateCadParams,
  GenerateCadResponse,
  GenerateMeshResponse,
  JobResponse,
  UploadResponse
} from "@/lib/types";

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

export async function uploadImage(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("image", file);

  return requestJson<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData
  });
}

export async function generateMesh(jobId: string): Promise<GenerateMeshResponse> {
  return requestJson<GenerateMeshResponse>("/api/generate-mesh", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId })
  });
}

export async function generateCad(
  jobId: string,
  params: GenerateCadParams
): Promise<GenerateCadResponse> {
  return requestJson<GenerateCadResponse>("/api/generate-cad", {
    method: "POST",
    body: JSON.stringify({
      job_id: jobId,
      ...params
    })
  });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/api/jobs/${jobId}`);
}
