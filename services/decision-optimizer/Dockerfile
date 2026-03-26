# Decision-optimizer service
#
# Build context: repository root.
#
#   docker build -f services/decision-optimizer/Dockerfile -t decision-optimizer:latest .

FROM python:3.11-slim

WORKDIR /app

COPY contracts/ /app/contracts/

# Install shared utilities (structured JSON logging — OBS-001)
COPY services/shared/ /tmp/shared_pkg/
RUN --network=host pip install --no-cache-dir /tmp/shared_pkg && rm -rf /tmp/shared_pkg

COPY services/decision-optimizer/requirements.txt ./requirements.txt
RUN --network=host pip install --no-cache-dir -r requirements.txt

COPY services/decision-optimizer/decision_optimizer/ ./decision_optimizer/
COPY services/decision-optimizer/rules/ ./rules/

ENV CONTRACT_DIR=/app/contracts
ENV RULES_FILE=/app/rules/default-rules.json
ENV MQTT_BROKER_HOST=localhost
ENV MQTT_BROKER_PORT=1883
ENV MQTT_AUDIENCE_STATE_TOPIC=adaptive/v1/default-tenant/site-01/audience-state
ENV PLAYER_WS_HOST=0.0.0.0
ENV PLAYER_WS_PORT=8765
ENV PLAYER_WS_PATH=/player/commands
ENV DECISION_LOOP_HZ=1.0
ENV STALE_SIGNAL_THRESHOLD_MS=5000
ENV HEALTH_PORT=8081
ENV LOG_LEVEL=INFO

EXPOSE 8765 8081

CMD ["python", "-m", "decision_optimizer.main"]
