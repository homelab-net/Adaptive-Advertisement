# Player service
#
# Build context: repository root (required so contracts/ can be copied in).
#
#   docker build -f services/player/Dockerfile -t player:latest .
#
# The RENDERER_BACKEND defaults to "stub" for CI. Set RENDERER_BACKEND=mpv
# when building for Jetson deployment (requires mpv installed on the base image).
#
# Fallback asset selection (rebuild NOT required for runtime changes):
#   BUILD-TIME  — place assets in services/player/fallback_bundle/ and rebuild.
#   RUNTIME     — mount a volume at FALLBACK_LIBRARY_PATH (/data/fallback-library)
#                 and drop assets there.  Write a "_selected" file (filename only)
#                 to pin a specific asset; player picks it up within
#                 FALLBACK_REFRESH_INTERVAL_S seconds without restarting.

FROM python:3.11-slim

WORKDIR /app

# Copy ICD contract schemas needed for runtime schema validation
COPY contracts/ /app/contracts/

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

# Install Python dependencies before copying service source
# (layer caching: dependencies change less often than source)
COPY services/player/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source
COPY services/player/player/ ./player/

# Copy fallback bundle directory.
# Any supported asset (PNG/JPG/MP4/WEBM/HTML) placed in
# services/player/fallback_bundle/ before building is baked into the image
# and auto-selected at startup (selection priority 4).
COPY services/player/fallback_bundle/ ./fallback_bundle/

# Generate built-in fallback slate — dark-navy 1920x1080 PNG (pure Python, no PIL).
# Always present in the image as the last-resort asset (selection priority 6).
# Skipped during auto-discovery if any other asset exists in bundle or library.
RUN python3 -c "
import struct, zlib
from pathlib import Path

def solid_png(w, h, r, g, b):
    sig = b'\x89PNG\r\n\x1a\n'
    def chunk(tag, data):
        payload = tag + data
        crc = zlib.crc32(payload) & 0xffffffff
        return struct.pack('>I', len(data)) + payload + struct.pack('>I', crc)
    ihdr = chunk(b'IHDR', struct.pack('>II5B', w, h, 8, 2, 0, 0, 0))
    row  = b'\x00' + bytes([r, g, b]) * w
    idat = chunk(b'IDAT', zlib.compress(row * h, 9))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

out = Path('/app/fallback_bundle/fallback-builtin.png')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(solid_png(1920, 1080, 14, 20, 35))
print(f'generated {out} ({out.stat().st_size} bytes)')
"

# Runtime configuration defaults
ENV PLAYER_CONTRACT_DIR=/app/contracts
ENV FALLBACK_BUNDLE_PATH=/app/fallback_bundle
ENV FALLBACK_ASSET_NAME=""
ENV FALLBACK_LIBRARY_PATH=/data/fallback-library
ENV FALLBACK_REFRESH_INTERVAL_S=60
ENV MANIFEST_STORE_PATH=/data/manifests
ENV ASSET_CACHE_PATH=/data/assets
ENV HEALTH_PORT=8080
ENV LOG_LEVEL=INFO
ENV RENDERER_BACKEND=stub
ENV MPV_IPC_SOCKET=/tmp/mpv-player.sock
ENV DECISION_OPTIMIZER_WS_URL=ws://decision-optimizer:8765/player/commands

EXPOSE 8080

CMD ["python", "-m", "player.main"]
