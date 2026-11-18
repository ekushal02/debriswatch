from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Config:
    data_dir: Path
    detector: str = 'demo'
    model_path: str = 'models/debris.pt'
    device: str = 'cpu'
    enable_camera: bool = False
    max_upload_mb: int = 250
    max_video_seconds: int = 1800

    @classmethod
    def from_env(cls):
        return cls(
            Path(os.getenv('DW_DATA_DIR', 'runtime')).resolve(),
            os.getenv('DW_DETECTOR', 'demo'),
            os.getenv('DW_MODEL_PATH', 'models/debris.pt'),
            os.getenv('DW_DEVICE', 'cpu'),
            os.getenv('DW_ENABLE_CAMERA', '0') == '1',
            int(os.getenv('DW_MAX_UPLOAD_MB', '250')),
            int(os.getenv('DW_MAX_VIDEO_SECONDS', '1800')),
        )
