from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "processing", "completed", "failed"]
Mode = Literal["upload", "mesh", "cad", "both"]


class DimensionsMm(BaseModel):
    width: float
    height: float
    thickness: float


class CadSummary(BaseModel):
    detected_outline: bool
    detected_holes: int
    estimated_dimensions_mm: DimensionsMm


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    message: str
    status_url: str


class UploadImageResponse(BaseModel):
    job_id: str
    image_url: str
    masked_image_url: str | None = None


class GenerateMeshRequest(BaseModel):
    job_id: str


class GenerateCadRequest(BaseModel):
    job_id: str
    known_width_mm: float | None = None
    known_height_mm: float | None = None
    thickness_mm: float | None = None
    mode: str | None = None


class ProcessRequest(BaseModel):
    job_id: str
    generate_mesh: bool = True
    generate_cad: bool = True
    generate_freecad: bool = True
    known_width_mm: float | None = None
    known_height_mm: float | None = None
    thickness_mm: float | None = None


class ProcessResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    message: str
    preview_model_url: str | None = None
    full_model_url: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    cad_summary: CadSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    freecad: dict[str, str] = Field(default_factory=dict)
    mesh_source: str | None = None
    mesh_is_high_fidelity: bool = False
    # additive fields (safe for existing frontend; new consumers can read them)
    provider: str | None = None
    mesh_face_count: int | None = None
    step_generated: bool = False
    step_quality: str | None = None
    step_method: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)



class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    message: str
    created_at: datetime
    preview_model_url: str | None = None
    full_model_url: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    cad_summary: CadSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    mode: Mode
    input_image_url: str | None = None
    masked_image_url: str | None = None
    error: str | None = None
    freecad: dict[str, str] = Field(default_factory=dict)
    mesh_source: str | None = None
    mesh_is_high_fidelity: bool = False
    # additive fields
    provider: str | None = None
    mesh_face_count: int | None = None
    step_generated: bool = False
    step_quality: str | None = None
    step_method: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    triposr_enabled: bool
    triposr_configured: bool
    rembg_available: bool
    cadquery_available: bool
    trimesh_available: bool
    opencv_available: bool
    luma_configured: bool
    csm_configured: bool
    tripo_api_configured: bool
    supported_image_formats: list[str]
    supported_video_formats: list[str]
