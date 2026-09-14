# VaultPi

Personal NAS + AI photo pipeline, built on a Raspberry Pi 4 and AWS.

## Why

- A Windows partition was eating ~1TB of laptop storage for two games — couldn't reclaim it without losing a "Google Drive" of my own.
- No real NAS existed — photos and files just piled up locally, no dedup, no tagging, no backup.
- The Pi 4 (8GB) was already running Portainer, n8n, and a personal site 24/7 — spare capacity going to waste.
- An external HDD had been written off as "too slow" — irrelevant for archival/backup use.

So: idle Pi + "useless" HDD → a NAS with AI photo tagging, near-duplicate detection, and natural-language search, backed up to S3 instead of one SD card.

## Architecture

```
[Nobara laptop] --Samba (LAN only)--> [Pi 4, Docker host]
                                        ├─ Portainer (existing)
                                        ├─ n8n (existing)
                                        ├─ Website, via Cloudflare Tunnel (existing)
                                        └─ Samba --> External HDD (USB 3.0)
                                                 │
                                        scheduled rclone sync
                                                 │
                                                 v
                                        [S3: saim-vaultpi-files]
                                                 │
                                        S3 event --> [Lambda: process_upload]
                                                 │
                                    ┌────────────┼────────────────┐
                                    │                             │
                          [Rekognition: labels]     [Bedrock Titan: image embeddings]
                                    │                             │
                                    └─────────────┬───────────────┘
                                                   v
                                        [DynamoDB: VaultPi-FileMetadata]
                                                   │
                              (separate scripts: dedup, text-to-photo search)
                                                   │
                                        [S3 Lifecycle --> Glacier, planned]

Weekly: docker-compose configs + n8n volume --> S3 (pi-config-backup/)
```

- Photos live local-first on the HDD (Samba, LAN-only), then sync to S3 on a schedule.
- Each S3 upload triggers a Lambda: Rekognition tags it, Bedrock Titan embeds it, both land in DynamoDB.
- A dedup script scans the embedding table for near-duplicates by cosine similarity.
- A search script embeds a text query the same way and returns the closest photo matches.

## Key decisions

- **One Pi, no redundant second Pi.** Accepted single point of failure on purpose, to force real lessons in resource contention on constrained hardware. Mitigated with a weekly backup of Docker configs + n8n data to S3.
- **Bedrock Titan, not self-hosted CLIP.** One managed `InvokeModel` call handles both image and text embeddings — no model to host, version, or package into a Lambda container.
- **Samba never touches the public tunnel.** The Pi is already internet-facing (Cloudflare Tunnel, for the website) — file-sharing stays strictly LAN-only instead of reusing that path.
- **Hybrid storage tiering.** Files stay local on the HDD first (fast, private, free), then sync to S3 for AI processing and offsite backup, with a Glacier lifecycle rule planned for cold data.

## How to use it

Connect first, either way:

- **LAN:** `anakafeel-pi.local` (mDNS via avahi — survives DHCP/router changes).
- **Tailscale:** install the app, log into the tailnet, then reach the Pi at `100.68.237.12` — same ports and URLs as LAN.

**Immich** — browse the photo library / upload from phone
- App or browser → `http://100.68.237.12:2283` (Tailscale) / `http://anakafeel-pi.local:2283` (LAN)
- Reads existing photo folders in place, read-only. Smart search / facial recognition are off on purpose — that's what the Bedrock pipeline is for.

![Immich photo timeline](docs/screenshots/immich-timeline.jpg)

**Photo Search** — describe a photo, get matches
- `http://anakafeel-pi.local:5678/webhook/photo-search`
- Type a description ("birthday cake", "dog at the beach"), hit Search.
- First query after a 6h-stale cache: ~55-60s (full table scan). After that: a few seconds.
- Bookmark it to your phone's home screen — opens full-screen, feels like a lightweight app.

![Photo Search results for "birthday cake"](docs/screenshots/photo-search.jpg)

**Duplicate Review** — clean up near-duplicates
- `http://anakafeel-pi.local:5678/webhook/duplicate-review`
- 10 pairs per page, `← Previous` / `Next →` via `?offset=`.
- "Quarantine this one" moves the file to `_quarantine/` on the HDD and deletes its S3 copy. The auth token the webhook now requires is attached automatically — just click.

![Duplicate Review with a blurred pair](docs/screenshots/duplicate-review.jpg)
*(Photos blurred on purpose — real near-duplicate pairs, mostly identifiable family photos. UI, scores, and buttons are real and unedited.)*

**Grafana** — VaultPi Overview dashboard
- `http://anakafeel-pi.local:3001` — login required.
- Pi + per-container CPU/RAM/disk, plus CloudWatch metrics (Lambda, DynamoDB, S3). Disk alerts fire to Discord before a mount fills up.

![Grafana VaultPi Overview dashboard](docs/screenshots/grafana-dashboard.jpg)

**Don't expect too much:**
- Photo Search / Duplicate Review are unauthenticated plain HTML — "on the LAN or tailnet" *is* the auth model.
- No offline support, no native mobile app beyond a home-screen bookmark.
- A workflow failing mid-run (n8n restart, bad path) gets you a blank page, not a friendly error.
- What does work: search results are genuinely useful, dedup catches real duplicates, and quarantine + S3 backup make a bad click recoverable.

## Lessons learned

- **Dedup found organizational debt, not just accidental copies.** ~14,800 embeddings → ~11,400 candidate duplicate pairs, but the big clusters were whole folders copied wholesale (`My Pictures` mirrored into `SAIM PERSONAL FILES`, overlapping iPhone DCIM folders, a Note 8 `DCIM`/`DCIM (1)` conflict) — not isolated re-saves.
- **Raw object counts lie.** Assumed ~73,700 objects under the photos prefix; the real eligible-image count (JPEG/PNG/HEIC only, after excluding `.aae`/`.dng`/`.cr2`/etc.) was ~14,800 — a fifth of that. Compute the filtered count up front next time.
- **Video was excluded from day one.** Rekognition and Bedrock embeddings are photo-only, and video files are too large to justify processing for no dedup/search benefit — `.mov`/`.mp4`/`.avi`/`.m4v` are skipped by the sync script.

## Repo structure

- `pi-configs/` — docker-compose files for services on the Pi (n8n, watchtower, samba, immich, monitoring)
- `scripts/` — sync, AI backfill, dedup, search, and backup/maintenance scripts that run on the Pi
- `config/` — non-secret config (e.g. photo source folders)
- `lambda/process_upload/` — the S3-triggered Lambda that tags and embeds each new photo
- `terraform/` — infra as code for the AWS side (IAM, S3, DynamoDB, Lambda)
- `ansible/` — config management for the Pi (Docker, HDD mount, Samba, n8n, Immich, Tailscale, monitoring, cron)
- `docs/screenshots/` — real screenshots of the running system, referenced above
