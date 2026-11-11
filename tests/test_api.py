import time
import pytest
from fastapi.testclient import TestClient
from app.config import Config
from app.main import create_app
from scripts.generate_demo import generate

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Config(tmp_path/'runtime'))) as c: yield c

def upload(client,tmp_path,seconds=10):
    path=generate(tmp_path/'demo.avi',fps=10,seconds=seconds)
    with path.open('rb') as f: response=client.post('/api/uploads',files={'file':('demo.avi',f,'video/x-msvideo')})
    assert response.status_code==201,response.text
    return response.json()['id']

def wait(client,jid):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        state=client.get(f'/api/jobs/{jid}').json()
        if state['status'] in {'completed','failed','stopped'}: return state
        time.sleep(.02)
    raise AssertionError('Job did not complete')

def test_full_workflow_alerts_snapshots_resolution_and_export(client,tmp_path):
    uid=upload(client,tmp_path)
    assert client.get(f'/api/uploads/{uid}/preview').headers['content-type']=='image/jpeg'
    started=client.post('/api/jobs',json={'upload_id':uid,'realtime':False})
    assert started.status_code==202,started.text
    jid=started.json()['id'];state=wait(client,jid)
    assert state['status']=='completed',state
    events=client.get('/api/events',params={'job_id':jid}).json()
    assert len([e for e in events if e['rule']=='inspect'])==3
    assert len([e for e in events if e['rule']=='priority'])==1
    assert all(e['status']=='open' for e in events)
    assert client.get('/api/events/summary',params={'job_id':jid}).json()=={'total':4,'unresolved':4}
    eid=events[0]['id']
    assert client.get(events[0]['snapshot_url']).status_code==200
    assert client.get(f'/api/jobs/{jid}/frame').status_code==200
    assert client.post(f'/api/events/{eid}/acknowledge').json()['status']=='acknowledged'
    assert client.post(f'/api/events/{eid}/resolve').json()['status']=='resolved'
    assert client.post(f'/api/events/{eid}/acknowledge').json()['status']=='resolved'
    assert client.get('/api/events/summary',params={'job_id':jid}).json()=={'total':4,'unresolved':3}
    csv=client.get('/api/events/export.csv').text
    assert eid in csv and 'resolved' in csv and 'media_seconds' in csv

def test_one_worker_and_stop(client,tmp_path):
    uid=upload(client,tmp_path,seconds=4)
    jid=client.post('/api/jobs',json={'upload_id':uid}).json()['id']
    assert client.post('/api/jobs',json={'upload_id':uid}).status_code==409
    assert client.post(f'/api/jobs/{jid}/stop').status_code==200
    assert wait(client,jid)['status']=='stopped'

def test_upload_and_source_validation(client):
    assert client.post('/api/uploads',files={'file':('bad.txt',b'hello')}).status_code==415
    assert client.post('/api/uploads',files={'file':('bad.mp4',b'not a video')}).status_code==422
    assert client.post('/api/jobs',json={}).status_code==422
    assert client.post('/api/jobs',json={'upload_id':'../../etc/passwd'}).status_code==404
    assert client.post('/api/jobs',json={'source_type':'camera'}).status_code==403
    assert client.get('/api/events/unknown/snapshot').status_code==404
    assert client.get('/api/events?limit=-1').status_code==422

def test_missing_weights_are_explicit(tmp_path):
    with TestClient(create_app(Config(tmp_path/'data',detector='yolo',model_path=str(tmp_path/'missing.pt')))) as c:
        assert c.post('/api/jobs',json={'upload_id':'anything'}).status_code==503

def test_demo_is_labeled(client):
    assert client.get('/api/health').json()['demo'] is True
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/openapi.json').status_code==200

def test_http_body_limit(tmp_path):
    with TestClient(create_app(Config(tmp_path/'data',max_upload_mb=1))) as c:
        response=c.post('/api/uploads',files={'file':('large.avi',b'x'*(3*1024*1024))})
        assert response.status_code==413
