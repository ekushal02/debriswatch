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

## Reuse the existing Jetson lab setup

On the Mac, copy a clean reviewed checkout to a directory inside your existing Jetson lab bind mount. Use the actual SSH host and confirm the container mount with `docker inspect jetson_labs_dev --format '{{json .Mounts}}'` on the Jetson. Transfer `models/debris.pt` separately after training.

On the Jetson:

```bash
docker exec -it jetson_labs_dev bash
conda activate yolo_gpu
cd /home/jetson_labs/debriswatch
python -m scripts.jetson_info
python -c "import cv2, torch, torchvision, ultralytics; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
ls -l /dev/video*
```

The class environment uses Python 3.10, whereas the demo dependency set includes a multipart pin that requires Python 3.11. Install web packages separately inside the class environment so the existing vision stack stays in place. Review the dry-run plan, then repeat without `--dry-run` if the plan is limited to web dependencies.

```bash
python -m pip install --dry-run 'fastapi==0.162.4' 'uvicorn==0.54.0' 'pydantic==2.14.3' 'python-multipart==0.0.32'
```

If the web dependencies cannot resolve on Python 3.10, use a compatible Jetson container with Python 3.11 and verified CUDA-enabled PyTorch. Rerun the import check after installation. The lab container in the class transcript used host networking, so a localhost-bound server can be reached through the following Mac tunnel, using the actual SSH host:

```bash
ssh -N -L 8000:127.0.0.1:8000 jetson@JETSON_HOST
```

Stop any Mac-local service using port 8000 before opening the tunnel. If the installed container uses bridge networking instead, verify its port mapping and bind address before using the tunnel. The camera must be mapped into the container.

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
