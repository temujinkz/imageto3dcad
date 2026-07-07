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
  cad_stl?: string;
};

export type FreeCADFiles = {
  step?: string;
  obj?: string;
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

export type ProcessResponse = {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  preview_model_url?: string;
  files: MeshFiles & CadFiles & {
    freecad_step?: string;
    freecad_obj?: string;
  };
  cad_summary?: CadSummary;
  warnings?: string[];
  freecad?: FreeCADFiles;
  mesh_source?: string | null;
  mesh_is_high_fidelity?: boolean;
};

export type JobResponse = {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  preview_model_url?: string;
  files?: ProcessResponse["files"];
  freecad?: FreeCADFiles;
  warnings?: string[];
  mesh_source?: string | null;
  mesh_is_high_fidelity?: boolean;
};

export type WorkflowStep =
  | "Ready"
  | "Converting format"
  | "Removing background"
  | "Uploading"
  | "Generating 3D model"
  | "Preparing CAD exports"
  | "Completed"
  | "Failed";

export type PipelineResult = {
  previewModelUrl?: string;
  files: ProcessResponse["files"];
  freecad?: FreeCADFiles;
  cadSummary?: CadSummary;
  warnings?: string[];
  meshSource?: string | null;
  meshIsHighFidelity?: boolean;
};

export type SelectedMedia = {
  files: File[];
  previewUrl: string;
  maskedPreviewUrl?: string;
  isVideo: boolean;
};
