"""Generate synthetic workflow footage; this is NOT a FOD training dataset."""
import argparse
from pathlib import Path
import cv2
import numpy as np


def generate(path, fps=15, seconds=10):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    writer = cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(640,480))
    if not writer.isOpened():
        raise RuntimeError('MJPG codec unavailable.')
    rng = np.random.default_rng(42)
    background = np.clip(rng.normal(60,6,(480,640,1)),0,255).astype('uint8')
    background = np.repeat(background,3,axis=2)
    try:
        for frame in range(int(fps*seconds)):
            t=frame/fps
            img=background.copy()
            if 1 <= t < 8:
                cv2.rectangle(img,(160,180),(205,215),(20,40,230),-1)
            if 3 <= t < 8:
                cv2.circle(img,(340,200),18,(30,220,30),-1)
                cv2.rectangle(img,(440,280),(475,315),(230,50,30),-1)
            if 8 <= t < 9:
                img[:]=0  # Simulated camera obstruction: must not resolve alerts.
            writer.write(img)
    finally:
        writer.release()
    return path

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='samples/demo.avi')
    args=parser.parse_args()
    print(generate(args.output))
