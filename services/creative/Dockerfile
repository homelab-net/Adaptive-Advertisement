# syntax=docker/dockerfile:1
# Creative service
#
# Build context: repository root.
#
#   docker build -f services/creative/Dockerfile -t creative:latest .

FROM python:3.11-slim

WORKDIR /app

COPY contracts/ /app/contracts/

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN --network=host pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

COPY services/creative/requirements.txt ./requirements.txt
RUN --network=host pip install --no-cache-dir -r requirements.txt

COPY services/creative/creative/ ./creative/
COPY services/creative/manifests/ ./manifests/

ENV CONTRACT_DIR=/app/contracts
ENV MANIFEST_DIR=/app/manifests
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8090
ENV LOG_LEVEL=INFO

EXPOSE 8090

CMD ["python", "-m", "creative.main"]
