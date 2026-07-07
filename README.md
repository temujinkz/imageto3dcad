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
- `POST /api/upload-image`
- `POST /api/jobs`
- `POST /api/jobs/{job_id}/generate-mesh`
- `POST /api/jobs/{job_id}/generate-cad`
- `GET /api/jobs/{job_id}`
- `GET /api/files/{job_id}/{filename}`

## Demo Flow

1. `POST /api/upload-image` with the user photo.
2. Receive a `job_id`.
3. `POST /api/jobs/{job_id}/generate-mesh`.
4. Poll `GET /api/jobs/{job_id}` until mesh files appear.
5. `POST /api/jobs/{job_id}/generate-cad`.
6. Poll `GET /api/jobs/{job_id}` until CAD files appear.
7. Download `cad.stl`, `cad.step`, `mesh.stl`, `mesh.obj`, or `mesh.glb` through `GET /api/files/{job_id}/{filename}`.

The legacy `POST /api/jobs` endpoint still exists for a one-shot upload-and-generate flow, but the job-first flow above is the recommended frontend path.

## Reliability / Fallback Mode

- Uploaded images are converted to `input.png` and preprocessed into `masked.png` immediately.
- If `rembg` fails, the backend keeps going with the original image.
- If TripoSR works, mesh output uses the real image-to-3D path.
- If TripoSR fails, the backend falls back to a simple CadQuery solid when possible.
- If CadQuery is also unavailable, the backend falls back again to a contour-based STL/OBJ mesh extrusion.
- If CAD generation cannot produce `STEP`, the backend still returns `DXF` and `STL` so the demo does not die.

## Processing Outline

1. Save upload as `storage/jobs/{job_id}/input.png`.
2. Remove background when available and save `masked.png`.
3. Try TripoSR for mesh reconstruction.
4. Fall back to a simple generated solid mesh if TripoSR is unavailable.
5. Detect simple geometry with OpenCV.
6. Generate a flat-part CAD draft with CadQuery when available.
7. Fall back to DXF + STL if STEP export is unavailable.

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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```

## Frontend: single-port mode vs. dev mode

For active frontend development (hot reload), run the frontend and backend as
two separate processes. `lib/api.ts` defaults to a relative/same-origin API
base URL (so the single-port build below works on any port), so for this
two-process workflow create `.env.local` with:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

```bash
npm install
npm run dev            # http://localhost:3000, calls the backend at :8000
```

To run the whole app — frontend and API — from a single port instead, build
a static export once and let the backend serve it directly:

```bash
npm run build           # writes the static export to ./out
python3 -m uvicorn app.main:app --port 8000
# open http://localhost:8000 — frontend and API both live here
```

`app/main.py` mounts `./out` (if present) after all `/api/*` routes, so API
routes always take priority over the static files. Rebuild with
`npm run build` after any frontend change to pick it up in this mode.

## TripoSR

TripoSR is optional because its setup can be heavy and GPU-dependent.

Configure:

```bash
export USE_TRIPOSR=true
export PHOTO2CAD_TRIPOSR_RUN_PY=/absolute/path/to/TripoSR/run.py
```

If TripoSR fails, the API does not crash. It falls back to a contour-based mesh.
If CadQuery is available during fallback, it prefers a simple generated solid before dropping to raw contour extrusion.

## Notes

- For the first version, CAD generation uses a rectangular base plus detected holes.
- `GET /api/jobs/{job_id}` returns progress, message, file URLs, preview URL, and CAD summary.
- File responses use full URLs intended for frontend consumption.
