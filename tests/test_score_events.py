from scripts.score_events import score

def row(t,rule='inspect',clip='a'):
    return dict(clip=clip,rule=rule,media_seconds=str(t))

def test_one_to_one():
    r=score([row(2),row(4)],[row(2.1),row(2.2),row(4.2)],.5)
    assert (r['tp'],r['fp'],r['fn'])==(2,1,0)

def test_rule_and_clip_separation():
    r=score([row(2)],[row(2,'priority'),row(2,clip='b')],1)
    assert (r['tp'],r['fp'],r['fn'])==(0,2,1)

def test_empty():
    assert score([],[],1)['precision'] is None
