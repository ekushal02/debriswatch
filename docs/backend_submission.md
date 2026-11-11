# Backend submission: DebrisWatch

Prepared: 10 November 2026. This is the backend plus an initial frontend implementation for the previously proposed Jetson debris-inspection project. It is not a claim that the earlier 3 November deadline was met.

## Assignment deliverables

| Requirement | Included deliverable |
| --- | --- |
| GitHub backup | Local Git repository and `scripts/backup_github.sh`; authenticated remote creation/push is pending |
| Python package list | Pinned `requirements.txt`, plus development and optional ML requirement files |
| Container image name | Build target `debriswatch-backend:0.1.0`; base `python:3.11-slim-bookworm` |
| README | Root `README.md` with setup, API, configuration, demo, model training and backup instructions |
| Runnable backend scripts | `app/` package and `python -m scripts.run_backend` |
| Frontend files | `app/static/index.html`, `style.css`, `app.js`; served at `/` |
| Tests | `tests/`; CI workflow in `.github/workflows/tests.yml` |

## What works in the tested demo

The API accepts a video, validates its format and limits, starts one background inspection, tracks colored demo objects inside a configured zone, creates timestamped alerts with snapshots, persists job/event records, and supports manual acknowledgment/resolution and CSV export. Recorded video uses media time so paced and unpaced processing follow the same duration rules. The generated scene triggers three individual alerts and one priority alert. Removing objects from the scene does not resolve these alerts.

The frontend exposes upload, convex-zone drawing, confidence and timing controls, start/stop, annotated frame polling, status/count/FPS displays, event evidence and CSV download. Its browser acceptance run is still pending.

## Validation record

Executed on Linux with Python 3.12:

- `python -m pytest`: **20 passed**, including an API integration run over a generated video.
- The integration run verifies three inspection events and one priority event, evidence retrieval, manual state transitions, complete summary counts and CSV content.
- Additional checks cover source/upload validation, concurrent-job rejection and stopping, missing model weights, persistence after restart, track timing/gaps, polygon rejection, grouped VOC conversion and duplicate-image leakage prevention.
- Live Uvicorn HTTP smoke test: health, dashboard HTML and OpenAPI returned HTTP 200.
- `python -m pip check`: no broken requirements.
- `python -m compileall -q app scripts tests`: passed.
- `node --check app/static/app.js` and `bash -n scripts/backup_github.sh`: passed.
- One non-failing test warning: Starlette deprecates its legacy HTTPX test-client transport; the pinned tests pass with that transport.

Docker is not available in this workspace, so the image build/run remains unverified. Chromium could not launch because the environment blocked a required socket operation, so no successful browser interaction or visual-layout result is claimed. The full FOD-A download, optional Ultralytics environment, actual YOLO weights, camera capture and Jetson GPU execution have not been tested.

## Remaining work before calling the ML project complete

1. Connect the GitHub account and push the repository; run its CI and give the instructor access.
2. Run the Docker build and the frontend acceptance checklist on the development machine.
3. Obtain FOD-A and trustworthy source-group information, prepare splits, train and evaluate the single-class model.
4. Identify the Jetson model/JetPack version, select a compatible CUDA environment, and test local inference and camera capture.
5. Record held-out detection metrics, staged-clip event precision/recall, false alarms on an empty scene, and sustained device performance. The proposal's performance goals remain targets.
6. Finish frontend acceptance and accessibility improvements, then prepare slides with measured results. The second project proposal is a separate future deliverable.

## Suggested short demonstration

Start the server, upload the generated demo, show the default zone and thresholds, run the clip, explain the four persistent findings, open one snapshot, acknowledge and resolve it, then export CSV and open `/docs`. State that the demo validates the backend workflow; trained FOD inference is the next integration milestone.
