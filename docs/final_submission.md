# Final submission runbook

## 1. Local verification on your Mac

From the repository root, using Python 3.11 or 3.12:

    python3 --version  # use Python 3.11 or 3.12
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements-dev.txt
    python -m pytest
    python -m scripts.generate_demo
    DW_DATA_DIR=runtime/local-check DW_DETECTOR=demo python -m scripts.run_backend

In another terminal, enter the repository root, activate the same environment, and run:

    source .venv/bin/activate
    python -m scripts.smoke_local

Open http://127.0.0.1:8000 and follow [frontend acceptance](frontend_checklist.md). The smoke script creates actual synthetic demo events in the server's runtime database and resolves one. Use a fresh DW_DATA_DIR if isolation is desired. Save browser screenshots during a separate paced run. The smoke test passed on Linux with Python 3.12, and all 23 automated tests passed. The exported API snapshot and 10-second annotated replay are linked in the README. Chromium could not start in that environment, so complete the interactive checklist on your Mac.

With Docker Desktop running, stop the Python server with Control-C to free port 8000, then run:

    docker compose up --build

From the second terminal run the smoke test again. Keep samples/demo.avi on the laptop because the smoke script sends the file to the container via HTTP. After the test, stop Compose with Control-C or run `docker compose down` in another terminal. Docker execution is pending.

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

Save a separate truth CSV and prediction CSV with the header `clip,rule,media_seconds`. Use one row per expected or observed alert, stable clip IDs, and rule names `inspect` or `priority`. Add the clip identifier to exported prediction rows. Review matches against evidence snapshots to check which object or cohort produced each event. The scorer pairs by clip, rule and time only.

    python -m scripts.score_events --truth truth.csv --predictions predictions.csv --tolerance 1

The JSON report defaults to `reports/event_metrics.json`. Its matched time differences use the video clock. Measure live added delay separately in wall-clock time.

## 5. README visuals and presentation

Capture real dashboard screenshots showing the inspection zone, priority alert, evidence snapshot and acknowledged/resolved state. Save under docs/media/ and embed with relative Markdown image links. Label synthetic demo visuals explicitly. Optionally capture a short MP4 or GIF. Do not commit private videos, database files, secrets, or unlicensed dataset assets.

Suggested presentation: problem and scope; dataset and detector; architecture; decision rules; UI demonstration; measured results and failures; limitations and next steps. Prepare a backup recording. Remove course-specific references from the public-facing README. Describe the prototype as operator assistance, not airfield clearance certification.

Submit repository link and any slides/recording explicitly required by the course portal. Verify submission deadlines and any instructor feedback separately.

## 6. Review, push and submit

1. Read the instructor's feedback and current submission page for the deadline, required files, and private-repository access. Verify Project 2 requirements separately.
2. Run the Mac checks above on the exact branch you intend to submit. If Docker or Jetson remains pending, record its status accurately in the slides and README.
3. Add a dashboard capture, real-model results and Jetson evidence as available. Keep raw footage, full datasets, model binaries and the runtime directory out of Git.
4. Review `git status`, `git diff`, and `git diff --check` before staging. Commit locally, then push your own branch and merge it into the submitted branch after review. Confirm the README images and replay link render on GitHub.
5. Submit the repository URL and any required slides or recording in the course portal. Open the submitted URL and check the portal shows the submission receipt. If the repo is private, verify the instructor can access it.
