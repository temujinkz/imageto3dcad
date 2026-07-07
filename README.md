# Photo2CAD Backend

FastAPI backend for a hackathon prototype that turns a single object image into estimated mesh files and a CAD draft.

## Folder Structure

```text
backend/
  app/
    main.py
    config.py
    models.py
    jobs.py
    routers/
      upload.py
      generate_mesh.py
      generate_cad.py
      files.py
    services/
      background.py
      triposr_service.py
      cad_service.py
      mesh_service.py
      image_geometry.py
  storage/
  requirements.txt
  .env.example
```

## Endpoints

- `GET /health`
- `GET /api/capabilities`
- `POST /api/jobs`
- `POST /api/generate-mesh`
- `POST /api/generate-cad`
- `GET /api/jobs/{job_id}`
- `GET /api/files/{job_id}/{filename}`

## Workflow

1. Upload a photo.
2. Save it as `storage/jobs/{job_id}/input.png`.
3. Remove background when available and save `masked.png`.
4. Try TripoSR for real mesh generation.
5. Fall back to contour extrusion if TripoSR is unavailable.
6. Detect simple geometry with OpenCV.
7. Generate a flat-part CAD draft with CadQuery when available.
8. Fall back to DXF + STL if CadQuery is unavailable.

## Output Files

Each job can create:

- `mesh.stl`
- `mesh.obj`
- `mesh.glb`
- `cad.step`
- `cad.stl`
- `cad.dxf`
- `metadata.json`

## Run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```

## TripoSR

TripoSR is optional because its setup can be heavy and GPU-dependent.

Configure:

```bash
export USE_TRIPOSR=true
export PHOTO2CAD_TRIPOSR_RUN_PY=/absolute/path/to/TripoSR/run.py
```

If TripoSR fails, the API does not crash. It falls back to a contour-based mesh.

## Notes

- For the first version, CAD generation uses a rectangular base plus detected holes.
- `GET /api/jobs/{job_id}` returns progress while queued or processing, and file URLs when completed.
- File responses use full URLs intended for frontend consumption.
