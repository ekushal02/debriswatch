from pathlib import Path
import cv2
import numpy as np
from .engine import Detection


class DemoDetector:
    """Color segmentation for generated demo clips ONLY, never a trained FOD model."""
    name = 'demo-color-detector'
    def detect(self, frame):
        mask = cv2.inRange(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), np.array([0, 130, 140]), np.array([179, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            if cv2.contourArea(contour) >= 35:
                x,y,w,h = cv2.boundingRect(contour)
                boxes.append(Detection((x,y,x+w,y+h), .99))
        return boxes


class YoloDetector:
    name = 'yolo-fod'
    def __init__(self, model_path, device):
        if not Path(model_path).is_file():
            raise ValueError(f'Trained model missing: {model_path}. Train the single-class debris model first.')
        from ultralytics import YOLO
        self.model = YOLO(model_path, task='detect')
        names = self.model.names
        if len(names) != 1 or str(names[0]).lower() != 'debris':
            raise ValueError('Expected single-class debris weights; general COCO weights are not a debris detector.')
        self.device = device

    def detect(self, frame):
        result = self.model.predict(frame, conf=.1, imgsz=320, device=self.device, verbose=False)[0]
        return [Detection(tuple(map(float, box)), float(score)) for box,score in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy())]


def make_detector(config):
    if config.detector == 'demo':
        return DemoDetector()
    if config.detector == 'yolo':
        return YoloDetector(config.model_path, config.device)
    raise ValueError('DW_DETECTOR must be demo or yolo.')


def quality_ok(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Conservative coarse obstruction/underexposure heuristic, not a camera-health model.
    return float(gray.mean()) >= 8 and float(gray.std()) >= 2
