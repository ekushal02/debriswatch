"""Run a real HTTP smoke test against a running demo server."""
import argparse
import csv
import io
import json
import time
from pathlib import Path
import httpx

def verify(base, video, output):
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=base, timeout=60) as c:
        def get(path):
            r=c.get(path); r.raise_for_status(); return r
        def post(path, **kw):
            r=c.post(path, **kw); r.raise_for_status(); return r.json()
        health=get('/api/health').json()
        if not health['demo']:
            raise RuntimeError('Use demo mode for the deterministic smoke test.')
        get('/'); get('/openapi.json')
        with video.open('rb') as f:
            up=post('/api/uploads', files={'file':(video.name,f,'video/x-msvideo')})
        job=post('/api/jobs',json={'upload_id':up['id'],'realtime':False})
        jid=job['id']
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            job=get('/api/jobs/'+jid).json()
            if job['status'] in {'completed','failed','stopped'}: break
            time.sleep(.25)
        assert job['status']=='completed',job
        q='?job_id='+jid
        events=get('/api/events'+q).json()
        assert sum(e['rule']=='inspect' for e in events)==3,events
        assert sum(e['rule']=='priority' for e in events)==1,events
        assert all(e['status']=='open' for e in events)
        for e in events:
            (output/(e['rule']+'-'+e['id']+'.jpg')).write_bytes(get(e['snapshot_url']).content)
        eid=events[0]['id']
        assert post('/api/events/'+eid+'/acknowledge')['status']=='acknowledged'
        assert post('/api/events/'+eid+'/resolve')['status']=='resolved'
        summary=get('/api/events/summary'+q).json()
        assert summary=={'total':4,'unresolved':3},summary
        exported=get('/api/events/export.csv'+q).text
        assert len(list(csv.DictReader(io.StringIO(exported))))==4
        (output/'events.csv').write_text(exported)
        (output/'workflow.json').write_text(json.dumps({'mode':'synthetic demo','job':job,'summary':summary,'events':events,'result':'passed'},indent=2))
        print('PASS: upload, inspection, 4 findings, snapshots, acknowledge, resolve, CSV.')
        print('Evidence:',output)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--base',default='http://127.0.0.1:8000')
    p.add_argument('--video',type=Path,default=Path('samples/demo.avi'))
    p.add_argument('--output',type=Path,default=Path('reports/demo-smoke'))
    a=p.parse_args(); verify(a.base,a.video,a.output)
