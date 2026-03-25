# Supervisor service — ICD-8
#
# Requires Docker socket access to restart managed containers:
#   docker run -v /var/run/docker.sock:/var/run/docker.sock supervisor:latest
#
# Build context: repository root.
#
#   docker build -f services/supervisor/Dockerfile -t supervisor:latest .

FROM python:3.11-slim

# docker CLI is needed for container restart commands.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

COPY services/supervisor/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir "aiohttp>=3.9,<4.0"

COPY services/supervisor/supervisor/ ./supervisor/

ENV HEALTH_POLL_INTERVAL_S=10
ENV SAFE_MODE_POLL_INTERVAL_S=15
ENV STORAGE_CHECK_INTERVAL_S=60
ENV RESTART_THRESHOLD=5
ENV FAST_FAIL_WINDOW_S=120
ENV BOOT_LOOP_THRESHOLD=3
ENV FAILURE_THRESHOLD=2
ENV HEALTH_PORT=8091
ENV DASHBOARD_API_URL=http://dashboard-api:8004
ENV PLAYER_CONTROL_URL=http://player:8080
ENV PLAYER_HEALTHZ_URL=http://player:8080/healthz
ENV DECISION_OPTIMIZER_HEALTHZ_URL=http://decision-optimizer:8081/healthz
ENV AUDIENCE_STATE_HEALTHZ_URL=http://audience-state:8082/healthz
ENV CREATIVE_HEALTHZ_URL=http://creative:8090/healthz
ENV DASHBOARD_API_HEALTHZ_URL=http://dashboard-api:8004/healthz
ENV PLAYER_CONTAINER=player
ENV DECISION_OPTIMIZER_CONTAINER=decision-optimizer
ENV AUDIENCE_STATE_CONTAINER=audience-state
ENV CREATIVE_CONTAINER=creative
ENV DASHBOARD_API_CONTAINER=dashboard-api
ENV DOCKER_RESTART_ENABLED=true
ENV STORAGE_DATA_PATH=/data
ENV STORAGE_WARN_PCT=80
ENV STORAGE_CRITICAL_PCT=90
ENV LOG_LEVEL=INFO

EXPOSE 8091

CMD ["python", "-m", "supervisor.main"]
