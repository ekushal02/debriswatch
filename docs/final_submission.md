# Release acceptance and presentation

## Local (Mac or Linux)
From repository root, use Python 3.11:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m scripts.generate_demo
python -m scripts.run_backend
```
Open http://127.0.0.1:8000. In another terminal activate the same venv:
```bash
python -m scripts.verify_workflow
```
This creates a new inspection and resolves one synthetic finding. Evidence is saved under reports/demo-smoke. Do not call this model accuracy. Follow frontend_checklist.md for interactive testing.

## Real model
Download FOD-A Pascal VOC from https://github.com/FOD-UNOmaha/FOD-data. Generate groups.csv, fill verified sequence/session groups, prepare data and train according to README. Use a separate GPU workstation if available. Use held-out data only for final evaluation. Record exact dataset provenance, split manifest, training parameters and weights checksum. On a Mac with Apple Silicon, try device mps if PyTorch supports it; otherwise cpu. Do not use CUDA device 0 on a Mac.

## Jetson (existing course container)
Identify the board, L4T release, CUDA state, camera and Python version first. Reuse the existing jetson_labs_dev / yolo_gpu environment only if compatible. Do not upgrade torch/torchvision or replace working NVIDIA wheels. Install only missing web packages using a verified compatible version set. Run inference with DW_DETECTOR=yolo DW_MODEL_PATH=models/debris.pt DW_DEVICE=0 DW_ENABLE_CAMERA=1. Use SSH forwarding rather than exposing the unauthenticated service. See jetson.md. Run tegrastats in a separate terminal and record board/power mode, FPS, memory and temperature during an unpaced video run and live camera run.

## Event evaluation
Record 20 real staged clips: 10 development and 10 held-out, covering transient debris, persistent debris, three persistent objects, outside-zone objects, removal, darkness, occlusion and clear surfaces. Freeze thresholds before held-out evaluation. Label expected alert times independently based on the configured persistence rules. For each clip export its event CSV; combine into predictions.csv with a clip column added. Truth and predictions require columns clip,rule,media_seconds, with rule inspect or priority. Use one row per event. Example command:
```bash
python -m scripts.score_events --truth truth.csv --predictions predictions.csv --tolerance 1
```
For the 10-minute empty-scene test report total false alerts separately. Time matching is an event-level approximation, not object identity matching; review ambiguous matches against snapshots. Negative delay indicates early alert. Do not report the synthetic demo as held-out evidence.

## README evidence
Capture a genuine dashboard screenshot during an inspection and a short recording showing detection, priority alert and manual resolution. Save sanitized assets in docs/media/ (no unrelated people, private addresses, credentials or restricted footage). Link them from README. Architecture diagram is already included. Label demo versus trained outputs clearly.

## Presentation outline
1. Problem and scope: close-range FOD inspection assistant, not clearance certification.
2. Dataset and grouping: number of images, classes merged, actual splits.
3. Architecture: camera, YOLO, tracking, decision engine, API, SQLite, UI.
4. Decision rules and uncertainty; show one and three objects.
5. Live demo and evidence review; backup video.
6. Detection and event metrics, hardware FPS, latency, memory, failure examples; report measured values only.
7. Limits and next steps (TensorRT optional).

## Before submitting
- [ ] Local tests and browser acceptance
- [ ] Docker build/run
- [ ] Trained debris model and held-out detection results
- [ ] Jetson CUDA and camera test
- [ ] Held-out event metrics and empty-scene results
- [ ] Actual dashboard media and README links
- [ ] Slides and backup demo recording
- [ ] GitHub main updated and accessible; exact submission deadline/portal verified
- [ ] Separate Project 2 proposal if required by instructor

No physical board, training data or model weights were available during preparation of this checklist.
