export type JobStatus = "queued" | "processing" | "completed" | "failed";

export type UploadResponse = {
  job_id: string;
  image_url: string;
  masked_image_url?: string;
};

export type MeshFiles = {
  stl?: string;
  obj?: string;
  glb?: string;
};

export type CadFiles = {
  step?: string;
  dxf?: string;
  stl?: string;
};

export type GenerateMeshResponse = {
  job_id: string;
  status: "completed";
  preview_model_url: string;
  files: MeshFiles;
};

export type CadSummary = {
  detected_outline: boolean;
  detected_holes: number;
  estimated_dimensions_mm: {
    width: number;
    height: number;
    thickness: number;
  };
};

export type GenerateCadParams = {
  known_width_mm?: number;
  known_height_mm?: number;
  thickness_mm?: number;
  mode: "flat_part";
};

export type GenerateCadResponse = {
  job_id: string;
  status: "completed";
  preview_model_url?: string;
  files: CadFiles;
  cad_summary?: CadSummary;
};

export type JobResponse = {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
};

export type GenerationMode = "mesh" | "cad";

export type GeneratedResult = {
  mode: GenerationMode;
  previewModelUrl?: string;
  files: MeshFiles & CadFiles;
  cadSummary?: CadSummary;
};
