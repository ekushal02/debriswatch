"""Train a compact single-class detector; training downloads initial weights if absent."""
import argparse
from pathlib import Path

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default='datasets/fod-yolo/data.yaml')
    parser.add_argument('--base',default='yolo11n.pt')
    parser.add_argument('--epochs',type=int,default=50)
    parser.add_argument('--batch',type=int,default=16)
    parser.add_argument('--device',default='cpu')
    args=parser.parse_args()
    if not Path(args.data).is_file():
        parser.error('Prepare the FOD-A dataset first.')
    from ultralytics import YOLO
    model=YOLO(args.base)
    model.train(data=args.data,epochs=args.epochs,batch=args.batch,imgsz=320,device=args.device,
                seed=42,project='runs',name='fod',exist_ok=False,patience=10,workers=2)
    print('Copy the resulting runs/fod*/weights/best.pt to models/debris.pt after reviewing validation results.')
