FROM python:3.11-slim

WORKDIR /app

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

# Install dependencies first (layer cache)
# pyproject.toml copied for reference (alembic env.py uses it for package lookup)
COPY services/dashboard-api/pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi>=0.111 \
    "uvicorn[standard]>=0.29" \
    "sqlalchemy[asyncio]>=2.0" \
    asyncpg>=0.29 \
    alembic>=1.13 \
    "pydantic>=2.6" \
    "pydantic-settings>=2.2" \
    "aiohttp>=3.9" \
    "aiomqtt>=2.0" \
    "python-multipart>=0.0.9"

COPY services/dashboard-api/dashboard_api/ ./dashboard_api/
COPY services/dashboard-api/alembic/ ./alembic/
COPY services/dashboard-api/alembic.ini ./

# Default data dirs (override via compose volume mounts)
RUN mkdir -p /data/manifests /data/assets

EXPOSE 8004

CMD ["python", "-m", "dashboard_api.main"]
