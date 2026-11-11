import pytest
from app.engine import Detection, RuleEngine
from app.schemas import InspectionSettings

def box(x=10, confidence=.9): return Detection((x,10,x+10,20),confidence)
def engine(**changes): return RuleEngine(InspectionSettings(zone=[(0,0),(1,0),(1,1),(0,1)], **changes))

def test_inspect_waits_for_dwell_and_deduplicates():
    e=engine(); results=[e.step([box()],t,100,100) for t in [0,.5,1,1.5,2]]
    assert [len(r['events']) for r in results]==[0,0,1,0,0]
    assert results[2]['events'][0]['rule']=='inspect'

def test_priority_requires_same_three_objects_and_duration():
    e=engine(); events=[]
    for t in [0,.5,1,1.5,2,2.5]: events+=e.step([box(10),box(35),box(65)],t,100,100)['events']
    assert len([r for r in events if r['rule']=='priority'])==1
    assert len([r for r in events if r['rule']=='inspect'])==3

def test_replaced_objects_cannot_inherit_priority_timer():
    e=engine(priority_seconds=1.5)
    for t in [0,.5,1]: assert not any(x['rule']=='priority' for x in e.step([box(10),box(35),box(60)],t,100,100)['events'])
    assert not any(x['rule']=='priority' for x in e.step([box(10),box(35),box(85)],1.5,100,100)['events'])

def test_missing_or_weak_frames_break_continuity():
    e=engine();e.step([box()],0,100,100)
    assert e.step([box(confidence=.3)],.5,100,100)['uncertain']
    assert not e.step([box()],1,100,100)['events']
    assert not e.step([box()],1.5,100,100)['events']
    assert e.step([box()],2,100,100)['events']

def test_large_timestamp_jump_does_not_imply_persistence():
    e=engine(); e.step([box()],0,100,100)
    assert not e.step([box()],10,100,100)['events']

def test_outside_zone_never_triggers_and_bad_quality_is_uncertain():
    e=RuleEngine(InspectionSettings(zone=[(.5,.5),(1,.5),(1,1),(.5,1)]))
    for t in [0,.5,1,1.5,2]:
        r=e.step([box()],t,100,100); assert r['count']==0 and not r['events']
    assert e.step([box()],2.5,100,100,quality_ok=False)['uncertain']

def test_nonmonotonic_time_is_rejected():
    e=engine();e.step([],2,100,100)
    with pytest.raises(ValueError): e.step([],1,100,100)

@pytest.mark.parametrize('zone', [[(0,0),(1,1),(0,1),(1,0)],[(0,0),(0,0),(1,1)],[(-.1,0),(1,0),(1,1)],[(0,0),(.001,0),(.001,.001)]])
def test_invalid_zones_rejected(zone):
    with pytest.raises(ValueError): InspectionSettings(zone=zone)
