# Audience-state service
#
# Build context: repository root.
#
#   docker build -f services/audience-state/Dockerfile -t audience-state:latest .

FROM python:3.11-slim

WORKDIR /app

COPY contracts/ /app/contracts/

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

COPY services/audience-state/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/audience-state/audience_state/ ./audience_state/

ENV CONTRACT_DIR=/app/contracts
ENV MQTT_BROKER_HOST=localhost
ENV MQTT_BROKER_PORT=1883
ENV MQTT_CV_OBSERVATION_TOPIC=adaptive/v1/default-tenant/site-01/cam-01/cv-observation
ENV MQTT_AUDIENCE_STATE_TOPIC=adaptive/v1/default-tenant/site-01/audience-state
ENV TENANT_ID=default-tenant
ENV SITE_ID=site-01
ENV CAMERA_ID=cam-01
ENV WINDOW_MS=5000
ENV PUBLISH_HZ=1.0
ENV MIN_STABILITY_OBSERVATIONS=3
ENV CONFIDENCE_FREEZE_THRESHOLD=0.5
ENV HEALTH_PORT=8082
ENV LOG_LEVEL=INFO

EXPOSE 8082

CMD ["python", "-m", "audience_state.main"]
