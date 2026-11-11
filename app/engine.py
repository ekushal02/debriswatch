"""Deterministic tracking + timestamp-based rules, independent of ML and HTTP."""
from dataclasses import dataclass
import math
import cv2
import numpy as np
from .schemas import InspectionSettings


@dataclass
class Detection:
    box: tuple[float, float, float, float]
    confidence: float


@dataclass
class Track:
    id: int
    box: tuple
    last_seen: float
    inside_since: float | None = None
    alerted: bool = False


def iou(a, b):
    w = max(0, min(a[2], b[2])-max(a[0], b[0]))
    h = max(0, min(a[3], b[3])-max(a[1], b[1]))
    inter = w*h
    return inter / max(1e-9, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)


class RuleEngine:
    def __init__(self, settings: InspectionSettings):
        self.s = settings
        self.tracks: dict[int, Track] = {}
        self.next_id = 1
        self.last_time = -1.0
        self.priority_since = None
        self.priority_sent = False
        self.priority_ids = set()

    def step(self, detections, timestamp, width, height, quality_ok=True):
        if not math.isfinite(timestamp) or timestamp < self.last_time:
            raise ValueError('Timestamps must be finite and monotonic.')
        gap = timestamp-self.last_time if self.last_time >= 0 else 0
        if gap > self.s.track_gap_seconds:
            for t in self.tracks.values():
                t.inside_since = None
            self.priority_since = None
            self.priority_ids.clear()
            self.priority_sent = False
        self.last_time = timestamp
        valid = [d for d in detections if all(math.isfinite(x) for x in (*d.box, d.confidence)) and d.box[2] > d.box[0] and d.box[3] > d.box[1]]
        weak = any(.1 <= d.confidence < self.s.confidence for d in valid)
        strong = [d for d in valid if d.confidence >= self.s.confidence] if quality_ok else []
        self.tracks = {i:t for i,t in self.tracks.items() if timestamp-t.last_seen <= self.s.track_gap_seconds}
        pairs = sorted([(iou(t.box, d.box), tid, di) for tid,t in self.tracks.items() for di,d in enumerate(strong)], reverse=True)
        matched_t, matched_d, assignments = set(), set(), {}
        for score, tid, di in pairs:
            if score >= .2 and tid not in matched_t and di not in matched_d:
                assignments[di] = tid
                matched_t.add(tid); matched_d.add(di)
        for tid,t in self.tracks.items():
            if tid not in matched_t:
                # Missed/weak frames break continuous dwell; IDs survive short gaps.
                t.inside_since = None
        poly = np.array(self.s.zone, np.float32)
        current, inside, events = [], [], []
        for di,d in enumerate(strong):
            tid = assignments.get(di)
            if tid is None:
                tid = self.next_id; self.next_id += 1
                self.tracks[tid] = Track(tid, d.box, timestamp)
            t = self.tracks[tid]
            t.box = d.box; t.last_seen = timestamp
            center = ((d.box[0]+d.box[2])/(2*width), (d.box[1]+d.box[3])/(2*height))
            in_zone = cv2.pointPolygonTest(poly, center, False) >= 0
            if in_zone:
                if t.inside_since is None:
                    t.inside_since = timestamp
                inside.append(tid)
                if not t.alerted and timestamp-t.inside_since + 1e-7 >= self.s.dwell_seconds:
                    events.append(dict(rule='inspect', track_ids=[tid], count=1, message=f'Debris track {tid} persisted for {self.s.dwell_seconds:g}s. Inspect and remove.'))
                    t.alerted = True
            else:
                t.inside_since = None
            current.append(dict(track_id=tid, box=list(d.box), confidence=d.confidence, in_zone=in_zone))
        ids = set(inside)
        # Require the same cohort to persist; replacement objects cannot inherit time.
        if len(ids) >= self.s.priority_count:
            cohort = self.priority_ids & ids
            if self.priority_since is None or len(cohort) < self.s.priority_count:
                self.priority_since = timestamp; self.priority_ids = ids; self.priority_sent = False
            else:
                self.priority_ids = cohort
            if not self.priority_sent and timestamp-self.priority_since + 1e-7 >= self.s.priority_seconds:
                events.append(dict(rule='priority', track_ids=sorted(self.priority_ids), count=len(self.priority_ids), message=f'{len(self.priority_ids)} debris tracks persisted for {self.s.priority_seconds:g}s. Priority cleanup.'))
                self.priority_sent = True
        else:
            self.priority_since = None; self.priority_sent = False; self.priority_ids.clear()
        return dict(detections=current, count=len(inside), uncertain=(not quality_ok or weak), events=events)
