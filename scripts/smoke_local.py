"""End-to-end HTTP acceptance check for the synthetic DebrisWatch demo.

Run the backend in a separate terminal first. Uses only Python's standard library.
This tests the demo workflow, NOT real FOD detection or Jetson performance.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request(base, method, endpoint, body=None, content_type=None, timeout=30):
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(base.rstrip("/") + endpoint, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = response.read()
            return response.status, payload, response.headers
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {endpoint}: HTTP {exc.code}: {detail[:600]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach backend at {base}: {exc.reason}") from exc


def api(base, method, endpoint, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    _, data, _ = request(base, method, endpoint, body, "application/json" if body is not None else None)
    return json.loads(data)


def upload_video(base, path):
    boundary = "debriswatch-" + uuid4().hex
    header = (f"--{boundary}\r\n"
              'Content-Disposition: form-data; name="file"; filename="demo.avi"\r\n'
              "Content-Type: video/x-msvideo\r\n\r\n").encode()
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    _, result, _ = request(base, "POST", "/api/uploads", body, f"multipart/form-data; boundary={boundary}")
    return json.loads(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--video", default="samples/demo.avi")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    base = args.base_url
    print("1/7 Checking backend health...")
    health = api(base, "GET", "/api/health")
    if not health.get("demo"):
        raise RuntimeError("This acceptance test requires DW_DETECTOR=demo. Do not run against YOLO mode.")
    print("   Demo mode confirmed (NOT a trained debris model).")

    path = Path(args.video)
    if not path.is_file():
        print("2/7 Generating synthetic video...")
        subprocess.run([sys.executable, "-m", "scripts.generate_demo", "--output", str(path)], check=True)
    else:
        print(f"2/7 Using existing video: {path}")
    print("3/7 Uploading video...")
    uploaded = upload_video(base, path)
    upload_id = uploaded["id"]
    status, _, _ = request(base, "GET", f"/api/uploads/{upload_id}/preview")
    assert status == 200, "Preview unavailable"

    print("4/7 Running unpaced inspection...")
    job = api(base, "POST", "/api/jobs", {"source_type": "video", "upload_id": upload_id, "realtime": False})
    job_id = job["id"]
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        job = api(base, "GET", f"/api/jobs/{job_id}")
        if job["status"] in {"completed", "failed", "stopped"}:
            break
        time.sleep(.25)
    else:
        raise RuntimeError(f"Job {job_id} timed out; inspect /api/jobs/{job_id}")
    if job["status"] != "completed":
        raise RuntimeError(f"Job ended with {job['status']}: {job.get('error')}")

    print("5/7 Checking event rules and saved JPEG evidence...")
    events = api(base, "GET", f"/api/events?job_id={job_id}")
    inspect = [e for e in events if e["rule"] == "inspect"]
    priority = [e for e in events if e["rule"] == "priority"]
    assert len(inspect) == 3, f"Expected 3 inspect findings, found {len(inspect)}"
    assert len(priority) == 1, f"Expected 1 priority finding, found {len(priority)}"
    assert all(e["status"] == "open" for e in events), "Events should start open"
    for event in events:
        assert event.get("snapshot_url"), "Missing evidence URL"
        status, data, headers = request(base, "GET", event["snapshot_url"])
        assert status == 200 and data[:2] == b"\xff\xd8", "Snapshot is not a JPEG"

    print("6/7 Checking acknowledgment, manual resolution, and counts...")
    event_id = events[0]["id"]
    acknowledged = api(base, "POST", f"/api/events/{event_id}/acknowledge")
    assert acknowledged["status"] == "acknowledged"
    resolved = api(base, "POST", f"/api/events/{event_id}/resolve")
    assert resolved["status"] == "resolved"
    summary = api(base, "GET", f"/api/events/summary?job_id={job_id}")
    assert summary == {"total": 4, "unresolved": 3}, summary

    print("7/7 Checking CSV export...")
    _, payload, _ = request(base, "GET", f"/api/events/export.csv?job_id={job_id}")
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    assert len(rows) == 4, f"Expected 4 CSV entries, found {len(rows)}"
    assert any(row["id"] == event_id and row["status"] == "resolved" for row in rows)

    print("\nPASS: Full synthetic demo API workflow verified.")
    print(f"Job ID: {job_id}")
    print(f"Results: {len(inspect)} inspect + {len(priority)} priority, 4 JPEGs, 1 manually resolved.")
    print("This does not verify model accuracy, browser visuals, camera access, or Jetson CUDA.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, AssertionError, OSError, ValueError) as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        sys.exit(1)
