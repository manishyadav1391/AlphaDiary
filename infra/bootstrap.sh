#!/usr/bin/env bash
#
# Prepare a fresh Ubuntu 24.04 host for the TJ stack (SRS 11.2).
#
#   sudo ./bootstrap.sh
#
# Installs Docker, adds swap, lays out /opt/tj and installs the systemd unit.
# It does NOT start the stack: .env has to be filled in first, and this
# script deliberately never writes a credential.
#
# Safe to re-run; every step checks before acting.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/tj}"
SWAP_FILE="/swapfile"
SWAP_SIZE_MB=2048
SERVICE_USER="${SUDO_USER:-${USER:-root}}"

log() { printf '\n==> %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

if [[ $EUID -ne 0 ]]; then
	echo "Run this with sudo." >&2
	exit 1
fi

# ---------------------------------------------------------------- swap
# A t3.small has 2 GB of RAM and no swap. A Docker build or a Postgres
# autovacuum can push past that, and the OOM killer takes the API with it.
log "Swap"
if swapon --show | grep -q "$SWAP_FILE"; then
	echo "    already active"
else
	fallocate -l "${SWAP_SIZE_MB}M" "$SWAP_FILE" 2>/dev/null ||
		dd if=/dev/zero of="$SWAP_FILE" bs=1M count="$SWAP_SIZE_MB" status=none
	chmod 600 "$SWAP_FILE"
	mkswap "$SWAP_FILE" >/dev/null
	swapon "$SWAP_FILE"
	grep -q "^${SWAP_FILE}" /etc/fstab || echo "${SWAP_FILE} none swap sw 0 0" >>/etc/fstab
	echo "    ${SWAP_SIZE_MB}MB added and persisted"
fi

# Prefer RAM; this box is memory-tight but not memory-starved.
sysctl -q -w vm.swappiness=10
grep -q "^vm.swappiness" /etc/sysctl.conf || echo "vm.swappiness=10" >>/etc/sysctl.conf

# -------------------------------------------------------------- packages
log "Base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg ufw ebtables >/dev/null

# ---------------------------------------------------------------- docker
log "Docker"
if have docker && docker compose version >/dev/null 2>&1; then
	echo "    already installed: $(docker --version)"
else
	install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
		gpg --dearmor -o /etc/apt/keyrings/docker.gpg
	chmod a+r /etc/apt/keyrings/docker.gpg

	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
		>/etc/apt/sources.list.d/docker.list

	apt-get update -qq
	apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
		docker-buildx-plugin docker-compose-plugin >/dev/null
	systemctl enable --now docker
	echo "    installed: $(docker --version)"
fi

if [[ "$SERVICE_USER" != "root" ]]; then
	usermod -aG docker "$SERVICE_USER"
	echo "    added ${SERVICE_USER} to the docker group (log out and back in)"
fi

# Container logs otherwise fill the disk, which on a 20 GB root is a matter
# of weeks.
log "Log rotation"
cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
systemctl restart docker

# ------------------------------------------------------------------ files
log "Application directory"
mkdir -p "$APP_DIR"
if [[ "$SERVICE_USER" != "root" ]]; then
	chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
fi
echo "    $APP_DIR ready"

# The repo layout is preserved, because docker-compose.yml refers to
# ./infra/Caddyfile and ./seed relative to itself.
mkdir -p "$APP_DIR/infra"
for file in docker-compose.yml .env.example infra/Caddyfile infra/docker-compose.build.yml; do
	source_path="$(dirname "$0")/../$file"
	if [[ -f "$source_path" ]]; then
		target="$APP_DIR/$file"
		[[ -f "$target" ]] || cp "$source_path" "$target"
	fi
done

# The seed files are bind-mounted by docker-compose.yml rather than baked into
# the image: the API image is built from apps/api, so the repo-root seed/ is
# outside its build context. Without this directory `app.cli seed` fails with
# "Not found: /srv/seed/charge_rates.json".
seed_source="$(dirname "$0")/../seed"
if [[ -d "$seed_source" ]]; then
	mkdir -p "$APP_DIR/seed"
	cp -n "$seed_source"/*.json "$APP_DIR/seed/" 2>/dev/null || true
	if [[ "$SERVICE_USER" != "root" ]]; then
		chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR/seed"
	fi
	echo "    seed/ copied ($(ls -1 "$APP_DIR/seed" | wc -l) files)"
else
	echo "    NOTE: seed/ not found beside this script; copy it to $APP_DIR/seed"
fi

# .env is never generated here: no script should invent a secret.
if [[ ! -f "$APP_DIR/.env" ]]; then
	echo "    NOTE: $APP_DIR/.env is missing. Copy .env.example and fill it in."
fi

# --------------------------------------------------------------- firewall
log "Firewall"
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
# Postgres and the API are reachable only inside the Docker network.
ufw --force enable >/dev/null
echo "    22, 80 and 443 open; everything else closed"

# ---------------------------------------------------------------- systemd
log "systemd unit"
if [[ -f "$(dirname "$0")/tj.service" ]]; then
	cp "$(dirname "$0")/tj.service" /etc/systemd/system/tj.service
	systemctl daemon-reload
	systemctl enable tj >/dev/null
	echo "    tj.service installed and enabled (not started)"
fi

cat <<EOF

Done. Next:

  1. Fill in ${APP_DIR}/.env    (APP_SECRET_KEY, APP_ENCRYPTION_KEY, POSTGRES_PASSWORD,
                                 DOMAIN, ACME_EMAIL, RESEND_API_KEY, S3_*)
  2. docker login ghcr.io
  3. cd ${APP_DIR} && docker compose pull
  4. sudo systemctl start tj
  5. docker compose exec api python -m app.cli create-user
  6. docker compose exec api python -m app.cli seed
  7. docker compose exec api python -m app.cli instruments
  8. docker compose exec api python -m app.cli holidays
  9. Register https://\${DOMAIN}/api/v1/kite/callback in the Kite Developer Console

EOF
