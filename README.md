# DebrisWatch

A local debris-inspection backend with a browser dashboard. Upload a video, define an inspection area, and keep an evidence-backed record of persistent objects that need operator review. This implements the backend and initial frontend for the DebrisWatch course proposal.

**Current release: functional demo and model-integration scaffold.** Demo mode detects colored shapes in a generated video; it is not a trained debris model. The YOLO adapter, dataset converter, training and evaluation entry points are included. FOD-A training, camera testing, Jetson benchmarks and TensorRT optimization remain to be completed. No accuracy or hardware-performance result is claimed.

## Run the demo

Use Python 3.11 or 3.12. Validation used Python 3.12 on Linux. Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.generate_demo
python -m scripts.run_backend
```

Windows: activate with `.venv\Scripts\Activate.ps1` in PowerShell. Open **http://127.0.0.1:8000** for the dashboard or **http://127.0.0.1:8000/docs** for interactive API documentation.

1. Choose `samples/demo.avi` in the dashboard.
2. Keep the default zone and thresholds, then start inspection.
3. The 10-second demo should create three individual inspection findings and one priority-cleanup finding. It includes a dark interval and subsequent object removal; the findings remain open.
4. Acknowledge a finding, review its snapshot, then select **Confirm removed** to resolve it. Export the event history as CSV.
5. For another area, select **Draw zone**, click 3–12 corners of a convex polygon in perimeter order, then select **Finish zone**. The API rejects crossing, concave or degenerate polygons.

The demo video is generated locally and is intentionally excluded from Git. No dataset download or GPU is required for this workflow. Use constant-frame-rate video: recorded-video timers use frame index / reported FPS.

## Included functionality

- FastAPI upload, job, snapshot, event-history and CSV endpoints; OpenAPI documentation.
- One background capture/inference worker; recorded video and opt-in host USB camera.
- Normalized inspection polygon, confidence threshold, lightweight IoU tracking, persistence rules and uncertainty flag.
- SQLite persistence for uploads, jobs and event state; evidence JPEGs on disk. Unfinished jobs become `interrupted` after a restart.
- Responsive HTML/CSS/JavaScript dashboard served by the backend. No Node build or third-party frontend service is required.
- FOD-A Pascal VOC conversion with explicit source-group splits, YOLO training/evaluation scripts, Docker packaging and GitHub Actions checks.

## Alert rules

| Rule | Default behavior |
| --- | --- |
| Inspect/remove | The same visible track's box center stays inside the zone for at least 1 second. One inspection alert per track. |
| Priority cleanup | At least 3 of the same track IDs stay inside the zone for at least 2 seconds. A changing crowd cannot inherit another group's timer. |
| Uncertain | Low-confidence candidates or the coarse dark/low-texture frame check indicate uncertainty. A capture failure also marks the job uncertain. |
| Resolution | Only an operator action resolves a finding. Disappearing detections, a finished job and a stopped feed never auto-resolve it. |

Matching uses greedy IoU overlap of at least 0.2. IDs survive short detection gaps up to 0.6 seconds, but a missed detection resets persistence timing. Larger timing gaps reset the timers too. Occlusion, camera motion and re-entry can create new IDs and duplicate findings; this is a stationary-camera baseline, not full re-identification. The quality heuristic is not a comprehensive occlusion detector. “No debris currently detected” is an observation, not clearance certification.

## Docker image

| Item | Name |
| --- | --- |
| Base image | `python:3.11-slim-bookworm` |
| Project image to build | `debriswatch-backend:0.1.0` |
| Compose service | `debriswatch` |

```bash
docker compose up --build
```

Or build explicitly: `docker build -t debriswatch-backend:0.1.0 .`.

Compose publishes `127.0.0.1:8000:8000` and persists inspection data in a named volume. The process runs as a non-root user. This image runs the **CPU demo**, not Jetson CUDA inference. It has not been built in the development workspace because Docker is unavailable there; the GitHub workflow includes a build check once pushed. No image has been published to a container registry. See [Jetson setup](docs/jetson.md) before choosing a GPU image for your device.

## Configuration

Environment variables are read at startup. `.env.example` is a reference; the Python launcher does not automatically load an `.env` file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DW_DETECTOR` | `demo` | `demo` or `yolo` |
| `DW_MODEL_PATH` | `models/debris.pt` | Local trusted single-class debris weights |
| `DW_DEVICE` | `cpu` | Ultralytics device, e.g. `0` for a compatible CUDA environment |
| `DW_ENABLE_CAMERA` | `0` | Set to `1` to enable host camera indices 0–9 |
| `DW_DATA_DIR` | `runtime` | SQLite, uploads and snapshots |
| `DW_MAX_UPLOAD_MB` | `250` | Maximum video file size in MiB |
| `DW_MAX_VIDEO_SECONDS` | `1800` | Maximum video/session duration |

Frames above 8.5 megapixels are rejected. Processing resizes the longest side to at most 960 pixels; YOLO receives an image size of 320. Camera access refers to the backend machine, not the browser's webcam. The API accepts saved upload IDs and camera indices, not arbitrary file paths or URLs.

Run exactly **one Uvicorn worker**. Job coordination is in-process; multiple workers/replicas are unsupported. Data survives restart, but the most recent live frame is held in memory; historical evidence remains available as event snapshots. Storage is not automatically purged. Back up the entire data directory with the service stopped.

This is a local single-operator prototype with no authentication. Keep it bound to localhost. Add authentication, TLS, quotas, retention and a shared job queue before offering it as a remote multi-user service.

## API quick reference

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Process configuration; not proof that a model can run |
| POST | `/api/uploads` | Multipart `file`; validate/decode video and return upload ID |
| GET | `/api/uploads/{id}/preview` | First-frame JPEG |
| POST | `/api/jobs` | Start one inspection; returns 202 |
| GET | `/api/jobs` | Most recent 100 jobs |
| GET | `/api/jobs/{id}` | Status, timing, count, uncertainty and error |
| POST | `/api/jobs/{id}/stop` | Request stop |
| GET | `/api/jobs/{id}/frame` | Latest annotated JPEG for the in-memory job |
| GET | `/api/events` | Optional `job_id`, `limit` (1–1000), `offset` |
| GET | `/api/events/summary` | Total and unresolved counts; optional `job_id` |
| POST | `/api/events/{id}/acknowledge` | Acknowledge an open finding |
| POST | `/api/events/{id}/resolve` | Operator-confirmed resolution |
| GET | `/api/events/{id}/snapshot` | Saved evidence JPEG |
| GET | `/api/events/export.csv` | All matching findings; optional `job_id` |

Start-request example after uploading:

```json
{
  "source_type": "video",
  "upload_id": "ID_RETURNED_BY_UPLOAD",
  "realtime": true,
  "settings": {
    "zone": [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]],
    "confidence": 0.5,
    "dwell_seconds": 1.0,
    "priority_count": 3,
    "priority_seconds": 2.0,
    "track_gap_seconds": 0.6
  }
}
```

`realtime: false` processes a recording without playback pacing while keeping the same media-time rules. `fps` is cumulative end-to-end throughput including pacing; `processing_ms` is the latest frame's detection/rule/annotation/evidence work, not a GPU-only inference benchmark. The dashboard displays the most recent 200 findings; its count and CSV cover all matching records.

## Training real debris detection

Use the official [FOD-A dataset repository](https://github.com/FOD-UNOmaha/FOD-data) and its Pascal VOC download links. Download/extract separately into `datasets/fod-voc`. Data and weights are not included in this repository. Preserve source attribution and review the dataset's usage terms before redistribution.

```bash
python -m scripts.prepare_dataset --input datasets/fod-voc --inventory groups.csv
```

Fill `group_id` for every annotation using source-video/session metadata. Keep related frames together; do not invent an independent group for every frame. If the downloaded archive does not expose reliable sequence identities, obtain them from the source or document a conservative grouping before evaluating. The converter deliberately does not guess this information.

```bash
python -m scripts.prepare_dataset --input datasets/fod-voc --groups-csv groups.csv --output datasets/fod-yolo
```

The converter merges object classes into `debris`, validates VOC boxes and complete group coverage, rejects exact-image leakage across splits, and creates approximately 70/15/15 train/validation/test partitions **by group count** (image ratios can differ). It writes a reproducible split manifest. At least three independent groups are required; more groups are preferable. Near-duplicate and scene leakage still need human review. Conversion has been tested on generated VOC fixtures; the complete FOD-A archive has not been processed in this workspace.

Train in a separate workstation/GPU environment, not the minimal demo environment:

```bash
python3 -m venv .venv-ml
source .venv-ml/bin/activate
python -m pip install -r requirements-ml.txt
python -m scripts.train --data datasets/fod-yolo/data.yaml --device 0
# After reviewing validation results, copy best.pt from the printed run path:
cp runs/fod/weights/best.pt models/debris.pt
python -m scripts.evaluate --weights models/debris.pt --device 0
DW_DETECTOR=yolo DW_MODEL_PATH=models/debris.pt DW_DEVICE=0 python -m scripts.run_backend
```

Use `--device cpu` if no compatible GPU is available; training will take longer. Subsequent training runs may use `runs/fod2`, etc. Initial training can download pretrained YOLO11n weights; the server never downloads a model. The server requires exactly one class named `debris` and rejects ordinary COCO weights. The optional ML dependency set and adapter have not been executed against a real trained model here. See [Jetson setup](docs/jetson.md) for platform-specific PyTorch requirements.

## Tests and submission

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

See [validation and submission status](docs/backend_submission.md) and [frontend acceptance steps](docs/frontend_checklist.md). GitHub Actions runs tests, generates the demo and builds the Docker image on push/PR. Model accuracy and staged-video event metrics are separate experiments, not inferred from unit tests.

## Back up to GitHub

Repository creation requires your authenticated GitHub account. The supplied helper creates a **private** repository by default and pushes the local branch, or pushes an existing `origin`.

```bash
gh auth login
# Set your actual commit identity if it is not already configured:
git config --global user.name "YOUR NAME"
git config --global user.email "YOUR EMAIL"
bash scripts/backup_github.sh debriswatch
```

Do not put tokens in source files. The `.gitignore` excludes datasets, runtime records, virtual environments, weights and training output. Invite the instructor to the private repository if required. The project image name is recorded above; a container-registry push is a separate step.

## Files

- `app/main.py`, `schemas.py`, `config.py`: HTTP interface and validation.
- `app/worker.py`, `detectors.py`, `engine.py`: capture, detection, tracking and event rules.
- `app/storage.py`: SQLite persistence.
- `app/static/`: frontend HTML, CSS and JavaScript.
- `scripts/`: launcher, demo generation, data conversion, training, evaluation, device information and GitHub backup.
- `tests/`: backend, rule, persistence and data-conversion checks.
- `requirements.txt`, `requirements-dev.txt`, `requirements-ml.txt`: runtime, tests and optional ML packages.
- `Dockerfile`, `compose.yaml`, `.github/workflows/tests.yml`: packaging and CI.

References: [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/), [Ultralytics prediction API](https://docs.ultralytics.com/modes/predict/), [FOD-A](https://github.com/FOD-UNOmaha/FOD-data), [Ultralytics Jetson deployment](https://docs.ultralytics.com/guides/nvidia-jetson/).
