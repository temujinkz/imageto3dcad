from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self.settings.storage_root.mkdir(parents=True, exist_ok=True)

    def create_job(self, mode: str, filename: str, options: dict) -> dict:
        job_id = uuid4().hex
        created_at = utcnow()
        job_dir = self.settings.storage_root / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        job = {
            "job_id": job_id,
            "mode": mode,
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "created_at": created_at,
            "updated_at": created_at,
            "filename": filename,
            "job_dir": str(job_dir),
            "input_path": str(job_dir / "input.png"),
            "masked_path": str(job_dir / "masked.png"),
            "outputs": {},
            "cad_summary": None,
            "warnings": [],
            "options": options,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._persist(job_id)
        return deepcopy(job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def update(self, job_id: str, **changes) -> dict:
        with self._lock:
            job = self._jobs[job_id]
            job.update(changes)
            job["updated_at"] = utcnow()
        self._persist(job_id)
        return self.get(job_id)  # type: ignore[return-value]

    def append_warning(self, job_id: str, warning: str) -> None:
        with self._lock:
            if warning not in self._jobs[job_id]["warnings"]:
                self._jobs[job_id]["warnings"].append(warning)
            self._jobs[job_id]["updated_at"] = utcnow()
        self._persist(job_id)

    def set_outputs(self, job_id: str, outputs: dict[str, str]) -> None:
        with self._lock:
            current = self._jobs[job_id]["outputs"]
            current.update(outputs)
            self._jobs[job_id]["outputs"] = current
            self._jobs[job_id]["updated_at"] = utcnow()
        self._persist(job_id)

    def _persist(self, job_id: str) -> None:
        job = self.get(job_id)
        if not job:
            return
        payload = deepcopy(job)
        payload["created_at"] = payload["created_at"].isoformat()
        payload["updated_at"] = payload["updated_at"].isoformat()
        metadata_path = Path(payload["job_dir"]) / "metadata.json"
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
