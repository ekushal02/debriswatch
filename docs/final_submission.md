# Final submission runbook

## 1. Local verification

From the repository root, using Python 3.11 or 3.12:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements-dev.txt
    python -m pytest
    python -m scripts.generate_demo
    DW_DETECTOR=demo python -m scripts.run_backend

In another terminal, activate the same environment and run:

    python -m scripts.smoke_local

Open http://127.0.0.1:8000 and follow [frontend acceptance](frontend_checklist.md). The smoke script creates actual synthetic demo events in the server's runtime database and resolves one. Use a fresh DW_DATA_DIR if isolation is desired. Save browser screenshots during a separate paced run. Demo findings are not AI accuracy evidence.

## 2. Train and evaluate the real model

Follow the root README's FOD-A conversion, grouping, training and evaluation commands. Preserve the source/group manifest and held-out split. Do not use the test set to tune the threshold. Copy the selected best.pt to models/debris.pt. Record class names, dataset size, split counts, training settings, test mAP50, precision and recall. Report results as measured, including missed targets.

## 3. Jetson deployment

Follow [Jetson setup](jetson.md). Identify the board and L4T version. Use the instructor's existing CUDA-enabled environment if compatible; avoid reinstalling working NVIDIA PyTorch. Confirm CUDA availability, then transfer the actual selected weights and test YOLO on a recording before live camera capture. Keep service local and use SSH forwarding. Record exact container image and dependency versions.

## 4. Evidence and evaluation

| Experiment | Proposed target | Actual |
|---|---|---|
| Held-out mAP50 | >= 0.80 | Not measured |
| Held-out debris recall | >= 0.90 | Not measured |
| Held-out staged event precision/recall | >= 0.85 each | Not measured |
| Empty-scene false alerts | <= 1 in 10 minutes | Not measured |
| Jetson throughput | >= 5 FPS | Not measured |
| Added alert delay after dwell | < 1 second | Not measured |

Stage twenty clips (ten development and ten held-out) with placement, brief appearance, outside-zone object, three persistent objects, occlusion and removal. Label expected rule, track/object identity and threshold-crossing time before evaluating. Match predicted and expected events one-to-one by rule, identity/cohort and a predeclared timing tolerance. Report TP/FP/FN and precision/recall; count false alerts during ten additional empty-scene minutes. Measure frame throughput with unpaced recording, plus wall-clock alert latency and memory with live capture. Never infer Jetson metrics from synthetic Mac tests.

## 5. README visuals and presentation

Capture real dashboard screenshots showing the inspection zone, priority alert, evidence snapshot and acknowledged/resolved state. Save under docs/media/ and embed with relative Markdown image links. Label synthetic demo visuals explicitly. Optionally capture a short MP4 or GIF. Do not commit private videos, database files, secrets, or unlicensed dataset assets.

Suggested presentation: problem and scope; dataset and detector; architecture; decision rules; UI demonstration; measured results and failures; limitations and next steps. Prepare a backup recording. Remove course-specific references from the public-facing README. Describe the prototype as operator assistance, not airfield clearance certification.

Submit repository link and any slides/recording explicitly required by the course portal. Verify submission deadlines and any instructor feedback separately.
