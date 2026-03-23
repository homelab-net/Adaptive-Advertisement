# Player service
#
# Build context: repository root (required so contracts/ can be copied in).
#
#   docker build -f services/player/Dockerfile -t player:latest .
#
# The RENDERER_BACKEND defaults to "stub" for CI. Set RENDERER_BACKEND=mpv
# when building for Jetson deployment (requires mpv installed on the base image).

FROM python:3.11-slim

WORKDIR /app

# Copy ICD contract schemas needed for runtime schema validation
COPY contracts/ /app/contracts/

# Install Python dependencies before copying service source
# (layer caching: dependencies change less often than source)
COPY services/player/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source
COPY services/player/player/ ./player/

# Copy fallback bundle
# A real deployment must mount or COPY a valid fallback asset here.
# The .gitkeep placeholder keeps the directory in version control but
# is NOT a valid asset — replace before running in production.
COPY services/player/fallback_bundle/ ./fallback_bundle/

# Runtime configuration defaults
ENV PLAYER_CONTRACT_DIR=/app/contracts
ENV FALLBACK_BUNDLE_PATH=/app/fallback_bundle
ENV FALLBACK_ASSET_NAME=fallback.jpg
ENV MANIFEST_STORE_PATH=/data/manifests
ENV ASSET_CACHE_PATH=/data/assets
ENV HEALTH_PORT=8080
ENV LOG_LEVEL=INFO
ENV RENDERER_BACKEND=stub
ENV MPV_IPC_SOCKET=/tmp/mpv-player.sock
ENV DECISION_OPTIMIZER_WS_URL=ws://decision-optimizer:8765/player/commands

EXPOSE 8080

CMD ["python", "-m", "player.main"]
