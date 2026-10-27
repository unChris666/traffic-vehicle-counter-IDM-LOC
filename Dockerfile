# syntax=docker/dockerfile:1
# CUDA user-space libraries; the host/Cloud Run supplies the NVIDIA driver.
FROM nvidia/cuda:12.6.3-base-ubuntu24.04@sha256:c87e78933f4c16e3272123bf2f75537306596d0fbaa395a29696a22786e5ee0e
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PROJ_NETWORK=OFF \
    LI_RUNTIME_MODE=bundled LI_AUTH_MODE=adc LI_WORKSPACE=/data \
    LI_CONFIG_ROOT=/app/config LI_CORE_PYTHON=/usr/bin/python3 \
    GRADIO_ANALYTICS_ENABLED=False GRADIO_TEMP_DIR=/data/gradio PORT=8080 \
    MPLCONFIGDIR=/data/matplotlib YOLO_CONFIG_DIR=/data/ultralytics
ENV PATH=/opt/venv/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/venv/lib/python3.12/site-packages/nvidia/cublas/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cufft/lib:/opt/venv/lib/python3.12/site-packages/nvidia/curand/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cusolver/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cusparse/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cudnn/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:/opt/venv/lib/python3.12/site-packages/nvidia/nvjitlink/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
WORKDIR /app
COPY deploy/requirements.lock /app/deploy/requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
COPY results/t7sl_modular/config ./config
# One installation layer also supports VFS builders with limited disk space.
# CUDA math/cuDNN libraries come from the pinned NVIDIA wheels required by Torch.
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    task_ca=/etc/ssl/certs/ca-certificates.crt; \
    if [ -f /run/secrets/proxy_ca ]; then task_ca=/run/secrets/proxy_ca; fi; \
    apt-get -o Acquire::https::CaInfo="$task_ca" update && \
    apt-get -o Acquire::https::CaInfo="$task_ca" install -y --no-install-recommends \
      python3 python3-venv python3-gdal python3-pyproj osmium-tool ffmpeg \
      libgl1 libglib2.0-0 ca-certificates cuda-nvrtc-dev-12-6 && \
    rm -rf /var/lib/apt/lists/* && /usr/bin/python3 -m venv /opt/venv && \
    PIP_CERT="$task_ca" python -m pip install --no-cache-dir --require-hashes -r deploy/requirements.lock && \
    python -m pip install --no-deps --no-build-isolation . && \
    python -m pip check && \
    python -m traffic_location.integration.container_runtime --verify && \
    dpkg-query -W > /app/deploy/os-packages.txt && \
    python -m pip freeze --all > /app/deploy/python-packages.txt && \
    useradd --uid 10001 --create-home appuser && mkdir -p /data && chown -R appuser:appuser /data
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "traffic_location.integration.container_runtime"]
