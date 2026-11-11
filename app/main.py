from contextlib import asynccontextmanager
import csv
import io
import json
from pathlib import Path
from uuid import uuid4
import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .config import Config
from .schemas import JobRequest
from .storage import Store
from .worker import Runner


class UploadLimitMiddleware:
    """Bound the entire HTTP body, including multipart overhead and chunked uploads."""
    def __init__(self, app, maximum):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        total = 0
        async def limited():
            nonlocal total
            message = await receive()
            total += len(message.get('body',b''))
            if total > self.maximum:
                raise HTTPException(413, 'Upload exceeds configured size limit.')
            return message
        headers = dict(scope.get('headers',[]))
        try:
            size = int(headers.get(b'content-length',b'0'))
        except ValueError:
            size = self.maximum+1
        if size > self.maximum:
            return await Response('Upload exceeds configured size limit.',status_code=413)(scope,receive,send)
        await self.app(scope,limited,send)


def create_app(config=None):
    config = config or Config.from_env()
    store = Store(config.data_dir)
    runner = Runner(config,store)
    @asynccontextmanager
    async def lifespan(app):
        yield
        runner.shutdown()
    app = FastAPI(title='DebrisWatch API',version='0.1.0',lifespan=lifespan,
                  description='Single-camera local inspection. Demo mode is color segmentation, not trained FOD detection.')
    app.add_middleware(UploadLimitMiddleware,maximum=(config.max_upload_mb*1024*1024)+1024*1024)
    app.state.store = store; app.state.runner = runner

    @app.get('/api/health')
    def health():
        return dict(status='ok', detector=config.detector, demo=config.detector=='demo',
                    weights_present=Path(config.model_path).is_file(), camera_enabled=config.enable_camera,
                    max_upload_mb=config.max_upload_mb, single_worker=True)

    @app.post('/api/uploads',status_code=201)
    def upload(file: UploadFile = File(...)):
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in {'.mp4','.avi','.mov','.mkv'}:
            raise HTTPException(415,'Upload MP4, AVI, MOV, or MKV video.')
        uid = uuid4().hex
        path = config.data_dir/'uploads'/f'{uid}{suffix}'
        try:
            size = 0
            with path.open('wb') as output:
                while block := file.file.read(1024*1024):
                    size += len(block)
                    if size > config.max_upload_mb*1024*1024:
                        raise HTTPException(413,'Video exceeds configured upload size.')
                    output.write(block)
            cap = cv2.VideoCapture(str(path))
            try:
                ok,frame = cap.read()
                fps = float(cap.get(cv2.CAP_PROP_FPS))
                frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if not ok or fps <= 0 or fps > 240 or frames <= 0:
                    raise HTTPException(422,'Cannot decode video or invalid timing. Re-encode with constant FPS.')
                if frame.shape[0]*frame.shape[1] > 8_500_000 or frames/fps > config.max_video_seconds:
                    raise HTTPException(422,'Video exceeds frame-size or duration limit.')
                preview = config.data_dir/'uploads'/f'{uid}.jpg'
                if not cv2.imwrite(str(preview),frame):
                    raise HTTPException(500,'Cannot create video preview.')
                metadata = dict(id=uid, fps=fps, frames=frames, duration=frames/fps, width=frame.shape[1], height=frame.shape[0],bytes=size)
            finally:
                cap.release()
            store.add_upload(uid,path,metadata)
            return metadata
        except Exception:
            path.unlink(missing_ok=True)
            (config.data_dir/'uploads'/f'{uid}.jpg').unlink(missing_ok=True)
            raise
        finally:
            file.file.close()

    @app.get('/api/uploads/{uid}/preview')
    def preview(uid: str):
        if not store.upload(uid):
            raise HTTPException(404,'Upload not found.')
        return FileResponse(config.data_dir/'uploads'/f'{uid}.jpg')

    @app.post('/api/jobs',status_code=202)
    def start(request: JobRequest):
        if config.detector == 'yolo' and not Path(config.model_path).is_file():
            raise HTTPException(503,'Trained debris weights are missing. Configure DW_MODEL_PATH.')
        if request.source_type == 'camera':
            if not config.enable_camera:
                raise HTTPException(403,'Camera disabled. Set DW_ENABLE_CAMERA=1 on the host.')
            source = request.camera_index
        else:
            record = store.upload(request.upload_id)
            if not record:
                raise HTTPException(404,'Upload not found.')
            source = record['path']
        try:
            return runner.start(request,source)
        except RuntimeError as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.get('/api/jobs')
    def jobs():
        return store.jobs()

    @app.get('/api/jobs/{jid}')
    def job(jid: str):
        item = runner.get(jid)
        if not item:
            raise HTTPException(404,'Inspection not found.')
        return item

    @app.post('/api/jobs/{jid}/stop')
    def stop(jid: str):
        item = runner.stop(jid)
        if not item:
            raise HTTPException(404,'Inspection not found.')
        return item

    @app.get('/api/jobs/{jid}/frame')
    def frame(jid: str):
        blob = runner.frame(jid)
        if blob is None:
            raise HTTPException(404,'No frame available for this inspection.')
        return Response(blob,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

    @app.get('/api/events/export.csv')
    def export(job_id: str | None = None):
        fields = ['id','job_id','created_at','media_seconds','rule','count','track_ids','message','status','acknowledged_at','resolved_at']
        def rows():
            stream = io.StringIO(); writer = csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
            writer.writeheader(); yield stream.getvalue(); stream.seek(0); stream.truncate(0)
            offset = 0
            while batch := store.events(job_id,limit=500,offset=offset):
                for event in batch:
                    writer.writerow(event)
                yield stream.getvalue(); stream.seek(0); stream.truncate(0)
                offset += len(batch)
        return StreamingResponse(rows(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="debriswatch-events.csv"'})

    @app.get('/api/events')
    def events(job_id: str | None = None, limit: int = Query(200,ge=1,le=1000), offset: int = Query(0,ge=0)):
        result = store.events(job_id,limit,offset)
        for item in result:
            item['snapshot_url'] = f"/api/events/{item['id']}/snapshot" if item['snapshot'] else None
            item.pop('snapshot',None)
        return result

    @app.get('/api/events/summary')
    def event_summary(job_id: str | None = None):
        return store.event_summary(job_id)

    @app.post('/api/events/{eid}/{action}')
    def transition(eid: str, action: str):
        if action not in {'acknowledge','resolve'}:
            raise HTTPException(404,'Unknown event action.')
        item = store.transition(eid,action)
        if not item:
            raise HTTPException(404,'Event not found.')
        return item

    @app.get('/api/events/{eid}/snapshot')
    def snapshot(eid: str):
        item = store.event(eid)
        if not item or not item['snapshot']:
            raise HTTPException(404,'Snapshot not found.')
        return FileResponse(config.data_dir/'snapshots'/item['snapshot'])

    static = Path(__file__).parent/'static'
    app.mount('/static',StaticFiles(directory=static),name='static')
    @app.get('/',include_in_schema=False)
    def home():
        return FileResponse(static/'index.html')
    return app


app = create_app()
