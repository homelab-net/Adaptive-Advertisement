# input-cv service
#
# Base image: nvcr.io DeepStream for Jetson (JetPack 6 / L4T r36).
# Freeze the exact tag once the target JetPack version is confirmed.
# Current placeholder targets DeepStream 7.0 on JetPack 6.
#
# Device passthrough (/dev/video0) must be declared in compose.yml, not here.
# Run with --device /dev/video0 or the equivalent compose `devices:` block.
# The service user is added to the `video` group at build time so that
# privileged: true is NOT required.

FROM nvcr.io/nvidia/deepstream-l4t:7.0-triton

ARG DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 if not already present in the base image layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3-pip \
        libgstreamer1.0-0 \
        gstreamer1.0-tools \
    && rm -rf /var/lib/apt/lists/*

# Create non-root service user; grant video group for /dev/video* access
RUN groupadd -f video \
    && useradd -r -u 999 -g video -s /sbin/nologin inputcv

WORKDIR /app

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN python3.11 -m pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

COPY services/input-cv/requirements.txt ./requirements.txt
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# Copy service source (repo-root context — consistent with other services)
COPY services/input-cv/ ./
RUN python3.11 -m pip install --no-cache-dir -e .

USER inputcv

# Environment variables with safe defaults (override via compose or runtime secrets)
ENV INPUT_CV_CONFIG_PATH=/app/config/camera-source.json \
    MQTT_HOST=localhost \
    MQTT_PORT=1883 \
    MQTT_CLIENT_ID=input-cv-01 \
    TENANT_ID=default \
    SITE_ID=site-01 \
    PIPELINE_ID=pipeline-01 \
    LOG_LEVEL=INFO

ENTRYPOINT ["python3.11", "-m", "input_cv.main"]
