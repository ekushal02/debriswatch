import copy
import logging
import threading
import time
from uuid import uuid4
import cv2
import numpy as np
from .detectors import make_detector, quality_ok
from .engine import RuleEngine
from .storage import now

log = logging.getLogger(__name__)


class Runner:
    """One local capture worker. Run uvicorn with exactly one worker process."""
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.lock = threading.RLock()
        self.thread = None
        self.stop_signal = threading.Event()
        self.current = None
        self.jpeg = None

    def start(self, request, source):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError('An inspection is already active. Stop it before starting another.')
            self.stop_signal = threading.Event()
            job = dict(id=uuid4().hex, created_at=now(), status='queued', source_type=request.source_type,
                       upload_id=request.upload_id, camera_index=request.camera_index, detector=self.config.detector,
                       settings=request.settings.model_dump(), frame_index=0, media_seconds=0, fps=0,
                       count=0, uncertain=False, signal='Waiting for frames', error=None)
            self.current = job; self.jpeg = None
            self.store.save_job(job)
            self.thread = threading.Thread(target=self._run, args=(request,source), name='debriswatch-capture', daemon=True)
            self.thread.start()
            return copy.deepcopy(job)

    def get(self, jid):
        with self.lock:
            if self.current and self.current['id'] == jid:
                return copy.deepcopy(self.current)
        return self.store.job(jid)

    def stop(self, jid):
        with self.lock:
            if self.current and self.current['id'] == jid and self.thread and self.thread.is_alive():
                self.stop_signal.set()
                self.current['status'] = 'stopping'
        return self.get(jid)

    def shutdown(self):
        self.stop_signal.set()
        if self.thread:
            self.thread.join(timeout=8)

    def frame(self, jid):
        with self.lock:
            return self.jpeg if self.current and self.current['id'] == jid else None

    def _update(self, **values):
        with self.lock:
            self.current.update(values)

    def _run(self, request, source):
        capture = None
        jid = self.current['id']
        try:
            detector = make_detector(self.config)
            capture = cv2.VideoCapture(source)
            if not capture.isOpened():
                raise ValueError('Cannot open video or camera. Check the file, codec, or camera permissions.')
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if not np.isfinite(fps) or fps <= 0 or fps > 240:
                if request.source_type == 'video':
                    raise ValueError('Video has invalid FPS; re-encode with a constant frame rate.')
                fps = 30
            total = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT))) if request.source_type == 'video' else 0
            engine = RuleEngine(request.settings)
            self._update(status='running', input_fps=fps, total_frames=total)
            begin = time.monotonic(); frames = 0; last_persist = begin
            while not self.stop_signal.is_set():
                ok, frame = capture.read()
                if not ok:
                    if request.source_type == 'camera':
                        raise ValueError('Camera feed unavailable. Existing alerts remain open.')
                    if frames == 0 or (total and frames < total-2):
                        raise ValueError('Video decode stopped before the expected end.')
                    break
                if frame.shape[0]*frame.shape[1] > 8_500_000:
                    raise ValueError('Maximum supported frame size is 8.5 megapixels.')
                # Bound inference/display size while preserving aspect ratio.
                scale = min(1, 960/max(frame.shape[:2]))
                if scale < 1:
                    frame = cv2.resize(frame, None, fx=scale, fy=scale)
                seconds = frames/fps if request.source_type == 'video' else time.monotonic()-begin
                if seconds > self.config.max_video_seconds:
                    raise ValueError('Inspection time limit reached. Start a new session.')
                start = time.monotonic()
                good = quality_ok(frame)
                detections = detector.detect(frame) if good else []
                h,w = frame.shape[:2]
                result = engine.step(detections, seconds, w, h, good)
                canvas = frame.copy()
                pts = np.array([(int(x*w),int(y*h)) for x,y in request.settings.zone], np.int32)
                cv2.polylines(canvas,[pts],True,(200,200,0),2)
                for d in result['detections']:
                    x1,y1,x2,y2 = map(int,d['box'])
                    color = (0,180,255) if d['in_zone'] else (150,150,150)
                    cv2.rectangle(canvas,(x1,y1),(x2,y2),color,2)
                    cv2.putText(canvas,f"#{d['track_id']} {d['confidence']:.2f}",(x1,max(14,y1-6)),cv2.FONT_HERSHEY_SIMPLEX,.45,color,1)
                if self.config.detector == 'demo':
                    cv2.putText(canvas,'DEMO - COLOR SEGMENTATION, NOT FOD AI',(12,22),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                encoded,jpeg = cv2.imencode('.jpg',canvas,[cv2.IMWRITE_JPEG_QUALITY,85])
                if not encoded:
                    raise ValueError('Frame encoding failed.')
                blob = jpeg.tobytes()
                for event in result['events']:
                    path = self.config.data_dir/'snapshots'/f'{uuid4().hex}.jpg'
                    path.write_bytes(blob)
                    self.store.add_event(jid,seconds,event,path.name)
                frames += 1
                duration = max(1e-6,time.monotonic()-start)
                signal = 'Uncertain' if result['uncertain'] else ('Debris detected' if result['count'] else 'No debris currently detected')
                with self.lock:
                    self.jpeg = blob
                    self.current.update(frame_index=frames, media_seconds=round(seconds,3), count=result['count'],
                                        uncertain=result['uncertain'], signal=signal,
                                        fps=round(frames/max(.001,time.monotonic()-begin),2), processing_ms=round(duration*1000,1))
                    if time.monotonic()-last_persist >= 1:
                        self.store.save_job(self.current); last_persist = time.monotonic()
                if request.realtime and request.source_type == 'video':
                    self.stop_signal.wait(max(0,frames/fps-(time.monotonic()-begin)))
            self._update(status='stopped' if self.stop_signal.is_set() else 'completed')
        except Exception as exc:
            log.exception('Inspection failed')
            self._update(status='failed', error=str(exc), uncertain=True, signal='Uncertain - inspection failed')
        finally:
            if capture is not None:
                capture.release()
            with self.lock:
                self.store.save_job(self.current)
