#!/bin/bash
# VaultPi weekly config/state backup: docker-compose files + n8n's named
# volume (workflows, credentials, SQLite DB), uploaded to S3. Mitigates the
# single-Pi single-point-of-failure risk (Decision 2). Does NOT touch the
# Samba-served photo library on the HDD - that's covered by sync_photos.sh.
set -uo pipefail

VAULT_DIR="$HOME/vaultpi"
LOG_DIR="$VAULT_DIR/logs"
LOG_FILE="$LOG_DIR/config_backup.log"
BACKUP_DIR="$VAULT_DIR/backups/config"
S3_REMOTE="vaultpi-s3:saim-vaultpi-files/pi-config-backup"
N8N_VOLUME="n8n_n8n_data"
KEEP=4
DATE="$(date +%Y%m%d)"
TS="$(date '+%Y-%m-%d %H:%M:%S %Z')"

COMPOSE_ARCHIVE="$BACKUP_DIR/pi-compose-configs-$DATE.tar.gz"
N8N_ARCHIVE="$BACKUP_DIR/n8n-data-$DATE.tar.gz"

mkdir -p "$LOG_DIR" "$BACKUP_DIR"

log() {
  echo "[$TS] $1" >> "$LOG_FILE"
}

log "=== Config backup started ==="

# --- 1. Tar up docker-compose.yml directories (configs only, no volume data) ---
if tar -czf "$COMPOSE_ARCHIVE" -C "$HOME" watchtower n8n vaultpi/samba 2>>"$LOG_FILE"; then
  SIZE=$(stat -c%s "$COMPOSE_ARCHIVE" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 0 ]; then
    log "Compose config archive created: $COMPOSE_ARCHIVE ($SIZE bytes)"
  else
    log "FAILED: compose config archive is zero bytes"
  fi
else
  log "FAILED: tar of compose config directories failed"
fi

# --- 2. Back up n8n's named volume via a temporary alpine container ---
if docker run --rm \
    -v "$N8N_VOLUME":/data:ro \
    -v "$BACKUP_DIR":/backup \
    alpine sh -c "tar czf /backup/$(basename "$N8N_ARCHIVE") -C /data ." 2>>"$LOG_FILE"; then
  SIZE=$(stat -c%s "$N8N_ARCHIVE" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 0 ]; then
    log "n8n volume archive created: $N8N_ARCHIVE ($SIZE bytes)"
  else
    log "FAILED: n8n volume archive is zero bytes"
  fi
else
  log "FAILED: n8n volume backup via alpine container failed"
fi

# --- 3. Upload both archives to S3 ---
for ARCHIVE in "$COMPOSE_ARCHIVE" "$N8N_ARCHIVE"; do
  if [ -s "$ARCHIVE" ]; then
    if rclone copy "$ARCHIVE" "$S3_REMOTE/" --log-file="$LOG_FILE" --log-level INFO; then
      log "Uploaded to S3: $S3_REMOTE/$(basename "$ARCHIVE")"
    else
      log "FAILED: rclone upload of $(basename "$ARCHIVE")"
    fi
  else
    log "SKIPPED upload: $(basename "$ARCHIVE") missing or empty"
  fi
done

# --- 4. Prune local backups, keep last $KEEP of each archive type (S3 copies untouched) ---
for PATTERN in "pi-compose-configs-*.tar.gz" "n8n-data-*.tar.gz"; do
  ls -t $BACKUP_DIR/$PATTERN 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r OLD; do
    rm -f "$OLD"
    log "Pruned old local backup: $OLD"
  done
done

log "=== Config backup finished ==="
