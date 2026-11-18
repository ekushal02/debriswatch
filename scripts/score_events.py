"""Score manually labeled held-out clips; one-to-one rule/time matching."""
import argparse
import csv
import json
from pathlib import Path

def read(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def score(truth,pred,tolerance):
    if tolerance<0: raise ValueError('Tolerance must be nonnegative.')
    # Dynamic programming per clip/rule: maximize matches, then minimize time error.
    keys={(r['clip'],r['rule']) for r in truth+pred}
    matches=[]
    for clip,rule in sorted(keys):
        a=sorted(float(r['media_seconds']) for r in truth if (r['clip'],r['rule'])==(clip,rule))
        b=sorted(float(r['media_seconds']) for r in pred if (r['clip'],r['rule'])==(clip,rule))
        n,m=len(a),len(b)
        dp=[[ (0,0.0,[]) for _ in range(m+1)] for _ in range(n+1)]
        for i in range(1,n+1):
            for j in range(1,m+1):
                opts=[dp[i-1][j],dp[i][j-1]]
                err=abs(a[i-1]-b[j-1])
                if err<=tolerance:
                    k,c,p=dp[i-1][j-1]
                    opts.append((k+1,c+err,p+[(a[i-1],b[j-1])]))
                dp[i][j]=max(opts,key=lambda x:(x[0],-x[1]))
        matches.extend(dict(clip=clip,rule=rule,expected=x,observed=y,delay_seconds=y-x) for x,y in dp[n][m][2])
    tp=len(matches); fp=len(pred)-tp; fn=len(truth)-tp
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
    return dict(tp=tp,fp=fp,fn=fn,precision=precision,recall=recall,f1=f1,tolerance_seconds=tolerance,matches=matches)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--truth',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--tolerance',type=float,default=1)
    p.add_argument('--output',type=Path,default=Path('reports/event_metrics.json'))
    a=p.parse_args(); result=score(read(a.truth),read(a.predictions),a.tolerance)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
