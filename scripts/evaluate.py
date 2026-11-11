"""Evaluate held-out detection performance. Does not invent targets or event metrics."""
import argparse
import json
from pathlib import Path

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default='datasets/fod-yolo/data.yaml')
    parser.add_argument('--weights',default='models/debris.pt')
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--output',default='reports/detection_metrics.json')
    args=parser.parse_args()
    from ultralytics import YOLO
    model=YOLO(args.weights)
    metrics=model.val(data=args.data,split='test',imgsz=320,device=args.device)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'weights':args.weights,'split':'test','metrics':{k:float(v) for k,v in metrics.results_dict.items()},'speed_ms_per_image':metrics.speed},indent=2))
    print(path)
