# Jetson deployment plan

The Jetson model and JetPack release have not been identified yet, and no hardware benchmark has been run. The shipped Docker image is a CPU/demo container, not a claimed CUDA deployment.

## Identify the device

From the project root on the Jetson:

```bash
python3 -m scripts.jetson_info
```

Save the device model, JetPack/L4T version, Python version, RAM, power mode and camera details for the experiment log. This script only reports local platform information and whether PyTorch/CUDA are available.

## Select a compatible environment

Use the official [Ultralytics Jetson installation guide](https://docs.ultralytics.com/guides/nvidia-jetson/) and [NVIDIA PyTorch installation instructions](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html) for that exact board and JetPack version. A generic PyPI PyTorch wheel is not evidence of working Jetson CUDA.

This application targets Python 3.11/3.12 for its validated CPU setup. Older Jetson installations can have substantially older Python versions; do not assume the stock system Python can install these pins. Choose a supported container/Python environment, or adapt and retest dependency pins. Do not upgrade the board OS or overwrite its CUDA stack just to match the demo Dockerfile.

Train on a separate workstation if possible. Transfer only the validated single-class `debris` weights. Install the backend and optional ML dependencies in the compatible environment without replacing a working NVIDIA-provided PyTorch/torchvision pair. Record the final environment with `python -m pip freeze` after installation and inference verification.

## Run after environment verification

Confirm `torch.cuda.is_available()` and a small local-model inference before starting the service:

```bash
DW_DETECTOR=yolo DW_MODEL_PATH=models/debris.pt DW_DEVICE=0 \
  DW_ENABLE_CAMERA=1 python -m scripts.run_backend
```

The UI opens on localhost and can use an uploaded recording or a host USB camera index. The baseline capture path uses OpenCV's default backend; CSI/GStreamer pipelines and container camera passthrough are not implemented. Start with a recording to isolate inference from camera problems.

For access from a laptop without exposing the service, forward port 8000 with SSH using your actual Jetson hostname. No remote authentication layer is bundled.

## Benchmark and acceptance

1. Fix the board power mode, input resolution, model, confidence and zone.
2. Warm up the model before measuring.
3. Use the API with `realtime: false` on a fixed video to measure unpaced throughput; the UI uses paced playback by default.
4. Record CPU/GPU memory, temperature, processing latency distribution, elapsed time and frame count. The displayed cumulative FPS is not a GPU-only benchmark.
5. Check a sustained live camera session and deliberate feed failure. Existing alerts must remain available.
6. Evaluate real staged clips with manually labeled events and an empty scene. Record false alarms separately from detection mAP.

The proposal's 5 FPS goal is an acceptance target, not a measured result. If it is missed, profile first. TensorRT/FP16 export is a future optimization; there is no tested export/runtime path in this release. Record any board-specific container's exact image tag/digest only after selecting and testing it.
