FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi>=0.111 \
    "uvicorn[standard]>=0.29" \
    "sqlalchemy[asyncio]>=2.0" \
    asyncpg>=0.29 \
    alembic>=1.13 \
    "pydantic>=2.6" \
    "pydantic-settings>=2.2" \
    "aiohttp>=3.9" \
    "python-multipart>=0.0.9"

COPY dashboard_api/ ./dashboard_api/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Default data dirs (override via compose volume mounts)
RUN mkdir -p /data/manifests /data/assets

EXPOSE 8004

CMD ["python", "-m", "dashboard_api.main"]
