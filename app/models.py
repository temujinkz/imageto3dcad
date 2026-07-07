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


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    message: str
    created_at: datetime
    preview_model_url: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    cad_summary: CadSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    mode: Mode
    input_image_url: str | None = None
    masked_image_url: str | None = None
    error: str | None = None
