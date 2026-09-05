#!/bin/bash
HDD_ROOT="/mnt/vaultpi-hdd"
S3_REMOTE="vaultpi-s3:saim-vaultpi-files/photos"
MANIFEST="$HOME/vaultpi/config/photo_sources.txt"
LOG="$HOME/vaultpi/logs/sync_photos.log"

mkdir -p "$HOME/vaultpi/logs"
echo "=== Sync started: $(date) ===" >> "$LOG"

while IFS= read -r folder; do
  [ -z "$folder" ] && continue
  SRC="$HDD_ROOT/$folder"
  DEST="$S3_REMOTE/$folder"
  if [ -d "$SRC" ]; then
    echo "Syncing: $folder" >> "$LOG"
    rclone copy "$SRC" "$DEST" \
      --exclude "*.mov" --exclude "*.MOV" \
      --exclude "*.mp4" --exclude "*.MP4" \
      --exclude "*.avi" --exclude "*.AVI" \
      --exclude "*.m4v" --exclude "*.M4V" \
      --exclude "*.zip" --exclude "*.ZIP" \
      --log-file="$LOG" --log-level INFO
  else
    echo "SKIPPED (not found): $folder" >> "$LOG"
  fi
done < "$MANIFEST"

echo "=== Sync finished: $(date) ===" >> "$LOG"
