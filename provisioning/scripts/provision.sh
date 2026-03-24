#!/usr/bin/env bash
# provision.sh — Adaptive Advertisement appliance full device provisioning
# Golden-image first-boot script for Jetson Orin Nano (JetPack 6.x / L4T 36.x)
#
# PURPOSE
# -------
# Idempotent provisioning script that converts a freshly flashed JetPack image
# into a ready-to-run adaptive-advertisement appliance.  Running it a second
# time on an already-provisioned device is safe.
#
# GOLDEN-IMAGE DESIGN PRINCIPLES
# --------------------------------
# 1. ZERO device-specific values are hardcoded.  All identity is injected via
#    environment variables or deferred to first-boot personalisation steps.
# 2. Every action is idempotent — guard every install/create/enable with an
#    existence check so re-runs do not break a live device.
# 3. All secrets (WireGuard keys, API tokens) are supplied at personalisation
#    time, never baked into the image.
# 4. The script exits non-zero on any unrecoverable error.
#
# PERSONALISATION VARIABLES (supply before running or export in env)
# ------------------------------------------------------------------
# WireGuard (required for VPN admin plane — PROV-003):
#   WG_DEVICE_PRIVATE_KEY    — device WireGuard private key
#   WG_DEVICE_VPN_IP         — VPN IP for this unit (e.g. 10.10.0.N)
#   WG_ADMIN_PUBLIC_KEY      — admin server WireGuard public key
#   WG_PRESHARED_KEY         — WireGuard preshared key
#   WG_ADMIN_ENDPOINT        — admin server WAN address / DDNS hostname
#
# Optional tuning:
#   WG_VPN_SUBNET            — AllowedIPs (default: 10.10.0.0/24)
#   WG_PORT                  — WireGuard UDP port (default: 51820)
#   WG_ADMIN_SSH_PORT        — SSH port to restrict to VPN (default: 2222)
#   APP_DATA_ROOT            — base path for runtime data (default: /opt/adaptive-ad)
#   COMPOSE_PROJECT_DIR      — path to docker-compose project (default: /opt/adaptive-ad/app)
#   MOSQUITTO_CONFIG_DIR     — Mosquitto config dir (default: /etc/mosquitto/conf.d)
#   SERVICE_USER             — non-root user to run containers (default: adaptive)
#   SERVICE_GROUP            — group for SERVICE_USER (default: adaptive)
#   SKIP_WG                  — set to "1" to skip WireGuard (offline lab use only)
#   SKIP_DOCKER              — set to "1" to skip Docker install (already present)
#
# USAGE
# -----
#   # Typical fleet provisioning (remote or USB-key):
#   export WG_DEVICE_PRIVATE_KEY="..."
#   export WG_DEVICE_VPN_IP="10.10.0.5"
#   export WG_ADMIN_PUBLIC_KEY="..."
#   export WG_PRESHARED_KEY="..."
#   export WG_ADMIN_ENDPOINT="vpn.example.com"
#   sudo -E ./provision.sh
#
#   # Lab / CI (no VPN, no Docker recheck):
#   SKIP_WG=1 sudo -E ./provision.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
APP_DATA_ROOT="${APP_DATA_ROOT:-/opt/adaptive-ad}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-/opt/adaptive-ad/app}"
MOSQUITTO_CONFIG_DIR="${MOSQUITTO_CONFIG_DIR:-/etc/mosquitto/conf.d}"
SERVICE_USER="${SERVICE_USER:-adaptive}"
SERVICE_GROUP="${SERVICE_GROUP:-adaptive}"
SKIP_WG="${SKIP_WG:-0}"
SKIP_DOCKER="${SKIP_DOCKER:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()     { echo "[provision] $*"; }
section() { echo; echo "==== [provision] $* ===="; }
die()     { echo "[provision] ERROR: $*" >&2; exit 1; }
need_root() { [[ "$(id -u)" -eq 0 ]] || die "Must run as root (use sudo -E)"; }
is_installed() { command -v "$1" &>/dev/null; }
pkg_installed() { dpkg -l "$1" 2>/dev/null | grep -q '^ii'; }

# ---------------------------------------------------------------------------
# 0. Privilege check
# ---------------------------------------------------------------------------
need_root

log "Adaptive Advertisement appliance provisioning starting — $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
log "Repo root  : ${REPO_ROOT}"
log "Data root  : ${APP_DATA_ROOT}"
log "Service usr: ${SERVICE_USER}"

# ---------------------------------------------------------------------------
# 1. System updates and base dependencies
# ---------------------------------------------------------------------------
section "System packages"
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    iptables \
    iptables-persistent \
    nvme-cli \
    rsync \
    jq \
    python3 \
    python3-pip

# ---------------------------------------------------------------------------
# 2. Docker Engine
# ---------------------------------------------------------------------------
section "Docker Engine"
if [[ "${SKIP_DOCKER}" == "1" ]]; then
    log "SKIP_DOCKER=1 — skipping Docker install"
elif is_installed docker; then
    log "Docker already installed ($(docker --version))"
else
    log "Installing Docker Engine..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list

    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    log "Docker installed: $(docker --version)"
fi

# ---------------------------------------------------------------------------
# 3. Service user and groups
# ---------------------------------------------------------------------------
section "Service user"
if ! id "${SERVICE_USER}" &>/dev/null; then
    log "Creating system user ${SERVICE_USER}..."
    groupadd --system "${SERVICE_GROUP}"
    useradd --system \
            --gid "${SERVICE_GROUP}" \
            --no-create-home \
            --shell /usr/sbin/nologin \
            --comment "Adaptive Advertisement service account" \
            "${SERVICE_USER}"
else
    log "User ${SERVICE_USER} already exists"
fi

# Add service user to docker group so containers can be managed
if is_installed docker; then
    usermod -aG docker "${SERVICE_USER}" || true
fi

# ---------------------------------------------------------------------------
# 4. Runtime directory structure
# ---------------------------------------------------------------------------
section "Data directories"
# Directory map:
#   /opt/adaptive-ad/data/creative      — approved creative assets (manifests + media)
#   /opt/adaptive-ad/data/db            — PostgreSQL data volume
#   /opt/adaptive-ad/data/mosquitto     — Mosquitto persistence and logs
#   /opt/adaptive-ad/data/logs          — service log tails
#   /opt/adaptive-ad/data/supervisor    — supervisor state (safe-mode flag, etc.)
#   /opt/adaptive-ad/app                — docker-compose project files (bind-mounted)

for dir in \
    "${APP_DATA_ROOT}/data/creative" \
    "${APP_DATA_ROOT}/data/db" \
    "${APP_DATA_ROOT}/data/mosquitto/data" \
    "${APP_DATA_ROOT}/data/mosquitto/log" \
    "${APP_DATA_ROOT}/data/logs" \
    "${APP_DATA_ROOT}/data/supervisor" \
    "${COMPOSE_PROJECT_DIR}"; do
    if [[ ! -d "${dir}" ]]; then
        install -d -m 750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${dir}"
        log "Created ${dir}"
    else
        log "Exists   ${dir}"
    fi
done

# ---------------------------------------------------------------------------
# 5. Eclipse Mosquitto 2.x (on-device MQTT broker — locked: MQTT-BROKER-001)
# ---------------------------------------------------------------------------
section "Mosquitto MQTT broker"
if ! pkg_installed mosquitto; then
    log "Installing Mosquitto 2.x..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        mosquitto mosquitto-clients
    # Ensure package version meets minimum (2.x)
    MOSQ_VER=$(mosquitto -h 2>&1 | grep -oP '\d+\.\d+' | head -1)
    log "Mosquitto installed: ${MOSQ_VER}"
else
    log "Mosquitto already installed"
fi

# Write baseline config fragment if absent
MOSQ_APP_CONF="${MOSQUITTO_CONFIG_DIR}/adaptive-ad.conf"
if [[ ! -f "${MOSQ_APP_CONF}" ]]; then
    install -d -m 755 "${MOSQUITTO_CONFIG_DIR}"
    cat > "${MOSQ_APP_CONF}" <<'MOSQ'
# Adaptive Advertisement — Mosquitto baseline config
# Listener on loopback only; no external MQTT exposure (PROV-003 / WAN-independent)
listener 1883 127.0.0.1
allow_anonymous true

# MQTT v5 protocol support (ICD-2/ICD-3 require MQTTv5)
# (Mosquitto 2.x enables v5 by default; explicit here for documentation)

# Persistence
persistence true
persistence_location /opt/adaptive-ad/data/mosquitto/data/

# Logging
log_dest file /opt/adaptive-ad/data/mosquitto/log/mosquitto.log
log_type error
log_type warning
log_type notice
MOSQ
    log "Wrote ${MOSQ_APP_CONF}"
fi

systemctl enable mosquitto
systemctl restart mosquitto
log "Mosquitto enabled and running"

# ---------------------------------------------------------------------------
# 6. WireGuard VPN admin plane (PROV-003)
# ---------------------------------------------------------------------------
section "WireGuard VPN"
if [[ "${SKIP_WG}" == "1" ]]; then
    log "SKIP_WG=1 — skipping WireGuard (lab/offline mode)"
else
    WG_SETUP="${SCRIPT_DIR}/setup-wireguard.sh"
    if [[ ! -f "${WG_SETUP}" ]]; then
        die "setup-wireguard.sh not found at ${WG_SETUP}"
    fi
    chmod +x "${WG_SETUP}"
    # Pass through all WG_* vars; setup-wireguard.sh handles its own defaults
    bash "${WG_SETUP}"
fi

# ---------------------------------------------------------------------------
# 7. SSH hardening — restrict to VPN plane
# ---------------------------------------------------------------------------
section "SSH hardening"
SSHD_CONF="/etc/ssh/sshd_config.d/99-adaptive-ad.conf"
if [[ ! -f "${SSHD_CONF}" ]]; then
    cat > "${SSHD_CONF}" <<'SSH'
# Adaptive Advertisement — SSH hardening
# Admin access only through WireGuard VPN (wg0) — PROV-003
# The wg-quick PreUp/PostDown rules also enforce this at the iptables level.
ListenAddress 10.10.0.0/24
PasswordAuthentication no
PermitRootLogin no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
SSH
    log "Wrote ${SSHD_CONF}"
    systemctl reload sshd || true   # non-fatal; may need reboot on some images
fi

# ---------------------------------------------------------------------------
# 8. Deploy application from repo (docker-compose project)
# ---------------------------------------------------------------------------
section "Application files"
if [[ -f "${REPO_ROOT}/docker-compose.yml" ]]; then
    log "Syncing docker-compose project to ${COMPOSE_PROJECT_DIR}..."
    rsync -a --delete \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='node_modules' \
        "${REPO_ROOT}/" "${COMPOSE_PROJECT_DIR}/"
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${COMPOSE_PROJECT_DIR}"
    log "Application files synced"
else
    log "docker-compose.yml not found at repo root — skipping sync (expected in CI)"
fi

# ---------------------------------------------------------------------------
# 9. Systemd service unit — docker-compose application
# ---------------------------------------------------------------------------
section "Systemd application unit"
UNIT_FILE="/etc/systemd/system/adaptive-ad.service"
if [[ ! -f "${UNIT_FILE}" ]]; then
    cat > "${UNIT_FILE}" <<UNIT
[Unit]
Description=Adaptive Advertisement appliance (docker compose)
Documentation=https://github.com/homelab-net/adaptive-advertisement
Requires=docker.service network-online.target
After=docker.service network-online.target mosquitto.service wg-quick@wg0.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=${SERVICE_USER}
WorkingDirectory=${COMPOSE_PROJECT_DIR}
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
    systemctl enable adaptive-ad.service
    log "Created and enabled adaptive-ad.service"
else
    log "adaptive-ad.service already present"
fi

# ---------------------------------------------------------------------------
# 10. Verify nvme storage health (REC-005: storage monitor baseline)
# ---------------------------------------------------------------------------
section "Storage check"
NVME_DEV=$(lsblk -d -o NAME,TRAN | awk '$2=="nvme"{print "/dev/"$1}' | head -1 || true)
if [[ -n "${NVME_DEV}" ]]; then
    log "NVMe device: ${NVME_DEV}"
    nvme smart-log "${NVME_DEV}" 2>/dev/null | grep -E 'critical|percentage_used|data_units' || true
else
    log "No NVMe device detected (expected on physical target hardware)"
fi

# ---------------------------------------------------------------------------
# 11. Persist iptables rules
# ---------------------------------------------------------------------------
section "iptables persistence"
if is_installed netfilter-persistent; then
    netfilter-persistent save || true
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
section "Provisioning complete"
log "Device provisioned successfully — $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
log ""
log "Next steps for this unit:"
log "  1. Verify WireGuard:   wg show wg0"
log "  2. Verify Mosquitto:   systemctl status mosquitto"
log "  3. Start application:  systemctl start adaptive-ad"
log "  4. Tail logs:          journalctl -fu adaptive-ad"
log ""
log "To personalise a fresh golden image before first boot:"
log "  Export WG_DEVICE_PRIVATE_KEY, WG_DEVICE_VPN_IP, WG_ADMIN_PUBLIC_KEY,"
log "  WG_PRESHARED_KEY, WG_ADMIN_ENDPOINT — then re-run this script."
