# image-to-3D-CAD

Turn a single object photo into a real 3D mesh (GLB/OBJ/STL) **and** a CAD STEP
file. Next.js frontend + FastAPI backend. Heavy 3D reconstruction runs on cloud
GPUs (Meshy / Tripo / fal), so your machine stays cool; a local, dependency-only
engine is the offline fallback so the output is **never a box**.

## What changed / how it works now

The old pipeline emitted a literal `.box()` whenever no 3D engine was configured
(which was always, on a laptop with no GPU) — so a perfume bottle came out as a
cuboid. That is fixed. The mesh step is now a **provider chain**:

```
IMAGE_TO_3D_PROVIDER=auto   # first available wins:
  wavespeed-hunyuan3d -> meshy -> tripo-api -> fal-hunyuan3d -> luma -> csm -> triposr -> silhouette
```

- **Cloud providers** (Meshy/Tripo/fal/…) run neural reconstruction on their
  GPUs and return a real textured mesh. Enabled by setting the matching API key.
- **`silhouette`** is a local, offline, zero-network engine (numpy/scipy/
  scikit-image/trimesh). It turns the background-removed silhouette into a real
  3D solid: a **solid of revolution** for bottle/cup/vase-like shapes, or a
  distance-transform **"inflated" pillow** for everything else. Stylized, not
  photoreal, but always a genuine 3D shape with depth. This is the guaranteed
  fallback — there is no `.box()` path anymore.
- Force one engine withh `IMAGE_TO_3D_PROVIDER=meshy|silhouette|mock|…`.

### STEP / CAD (the priority output)

Two tracks, best-first, for an AutoCAD-openable STEP — never a bounding box:

1. **Gemini parametric** (`GEMINI_API_KEY`): Gemini looks at the photo and
   returns a stack of CAD primitives (e.g. perfume = cylinder body + frustum
   shoulder + neck + cap) with millimetre dimensions, which CadQuery turns into a
   **clean, small, editable STEP** (~15–30 KB). Ideal for AutoCAD.
2. **Tessellated solid** (no key needed): the reconstructed mesh is sewn into a
   STEP solid via OpenCASCADE — faithful to the shape, faceted, larger (~5–15 MB).
3. If neither is possible, STL/OBJ are still exported and `step_generated` is
   `false` with a clear reason.

Response metadata: `step_generated`, `step_quality`
(`parametric_approximate` | `tessellated`), `step_method`.

## API keys (all optional; put them in `.env.local`, which is gitignored)

| Key | Provider | Purpose |
|-----|----------|---------|
| `WAVESPEED_API_KEY` | wavespeed.ai (pay-per-use) | **Recommended.** Hunyuan3D V3 high-fidelity mesh on WaveSpeed's GPU. Tried first in `auto`. |
| `MESHY_API_KEY` | meshy.ai (API is paid) | High-fidelity mesh on Meshy's GPU. |
| `GEMINI_API_KEY` | Google AI Studio | **Recommended.** Clean parametric STEP for AutoCAD (called over REST — no SDK). |
| `TRIPO_API_KEY` | platform.tripo3d.ai | Fallback cloud mesh provider. |
| `FAL_KEY` (+`FAL_MODEL`) | fal.ai | Optional SOTA geometry (Hunyuan3D-2 / TRELLIS). |
| `LUMA_API_KEY` / `CSM_API_KEY` | Luma / CSM | Optional cloud providers. |

With **no keys at all**, you still get a real 3D mesh (silhouette engine) and a
tessellated STEP. With `MESHY_API_KEY` + `GEMINI_API_KEY` you get a
high-fidelity mesh **and** a clean parametric STEP.

> Security: `.gitignore` ignores every `.env*` except `.env.example`. Never
> commit real keys. The repo is public.

## Endpoints

- `GET /health`
- `GET /api/capabilities` — reports which providers/keys are configured
- `POST /api/upload` (also `POST /api/upload-image`) — upload image(s)/video
- `POST /api/process` — synchronous: runs mesh + CAD + FreeCAD, returns everything
- `POST /api/generate` / `POST /api/jobs` — upload + queue the full pipeline (async)
- `POST /api/jobs/{job_id}/generate-mesh` / `.../generate-cad` — async single steps
- `GET /api/jobs/{job_id}` — status/progress/artifacts
- `GET /api/files/{job_id}/{filename}` (alias: `GET /api/jobs/{job_id}/artifacts/{filename}`)

### Response fields (additive; existing frontend still works)

`preview_model_url`, `files{glb,obj,stl,step,dxf,cad_stl,…}`, `freecad{step,obj}`,
`mesh_source`, `mesh_is_high_fidelity`, `cad_summary`, `warnings`, plus new:
`provider`, `mesh_face_count`, `step_generated`, `step_quality`, `step_method`,
`quality_warnings`.

## Output files (`storage/jobs/{job_id}/`)

```
input.png              # original upload (normalized to PNG)
masked.png             # background-removed, cropped, centered
normalized.png         # debug copy of the model-input image
mesh.glb / .obj / .stl # the 3D model (centered, cleaned, normalized)
cad.step               # STEP (parametric or tessellated)
cad.stl                # solid as STL
cad.dxf                # 2D outline drawing
freecad.step / .obj    # FreeCAD-friendly copies
logs/pipeline.json     # provider, face count, bbox, step quality, timings
metadata.json          # full job record
```

## Run

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # CPU-only; no torch/GPU needed
cp .env.example .env.local               # then add your keys to .env.local
python3 -m uvicorn app.main:app --reload --port 8000
```

Frontend (dev, hot reload) — set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
in `.env.local`, then:

```bash
npm install
npm run dev            # http://localhost:3000
```

Single-port build (frontend + API on one port):

```bash
npm run build          # writes ./out
python3 -m uvicorn app.main:app --port 8000   # open http://localhost:8000
```

### Try a sample image

```bash
JOB=$(curl -sF image=@perfume.jpg -F background_removal=true localhost:8000/api/upload | jq -r .job_id)
curl -s -X POST localhost:8000/api/process -H 'content-type: application/json' \
  -d "{\"job_id\":\"$JOB\",\"generate_mesh\":true,\"generate_cad\":true,\"generate_freecad\":true}" | jq
# artifacts land in storage/jobs/$JOB/
```

## Notes / known limitations

- A single image cannot recover the truly hidden back of an object; cloud
  providers hallucinate a plausible back, the silhouette engine assumes symmetry.
- STEP is **approximate**: parametric (primitive fit) or tessellated (faceted),
  not an exact CAD reverse-engineer. `step_quality` says which.
- The local silhouette engine is stylized (reports `mesh_is_high_fidelity:false`);
  add `MESHY_API_KEY` for photoreal geometry.
- Mac/CPU only, no torch required. `TripoSR` remains supported if you set
  `PHOTO2CAD_TRIPOSR_RUN_PY` to an installed checkout (needs torch).

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

`tests/test_pipeline.py` asserts the live upload→process path produces a real 3D
mesh (face count > 12, i.e. not a box), a STEP (or a clear reason), debug
artifacts, and that a total provider failure fails the job loudly instead of
returning a box. Provider network calls are mocked, so tests run offline.
