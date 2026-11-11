"""Read-only checks to select a Jetson runtime; never replaces CUDA/PyTorch."""
import platform
from pathlib import Path
print('Architecture:',platform.machine())
print('Python:',platform.python_version())
for path in ['/proc/device-tree/model','/etc/nv_tegra_release']:
    p=Path(path)
    if p.exists(): print(path+':',p.read_text(errors='replace').replace('\x00','').strip())
try:
    import torch
    print('PyTorch:',torch.__version__,'CUDA runtime:',torch.version.cuda,'CUDA available:',torch.cuda.is_available())
except ImportError:
    print('PyTorch not installed in this Python environment.')
