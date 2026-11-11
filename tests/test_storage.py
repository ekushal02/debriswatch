from app.storage import Store,now

def test_restart_preserves_events_and_marks_unfinished_jobs(tmp_path):
    s=Store(tmp_path)
    s.save_job(dict(id='job',created_at=now(),status='running'))
    eid=s.add_event('job',2,dict(rule='inspect',count=1,track_ids=[1],message='Inspect'),'image.jpg')
    s.transition(eid,'acknowledge')
    restarted=Store(tmp_path)
    assert restarted.job('job')['status']=='interrupted'
    assert restarted.event(eid)['status']=='acknowledged'
    restarted.transition(eid,'resolve')
    assert restarted.event(eid)['resolved_at']
