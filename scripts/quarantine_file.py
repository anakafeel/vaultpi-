#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import shutil
import sys

import boto3

HDD_ROOT = "/mnt/vaultpi-hdd"
QUARANTINE_DIR = os.path.join(HDD_ROOT, "_quarantine")
LOG_PATH = "/home/anakafeel/vaultpi/logs/quarantine.log"
BUCKET = "saim-vaultpi-files"
S3_PREFIX = "photos"
REGION = "us-east-1"


def log(line):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "rel_path",
        help="file path relative to /mnt/vaultpi-hdd, e.g. 'My Pictures/foo.jpg'",
    )
    args = parser.parse_args()
    rel_path = args.rel_path

    result = {"ok": False, "rel_path": rel_path}

    # Reject absolute paths, path traversal, and anything already inside
    # _quarantine - a double-quarantine attempt (e.g. a stale button click
    # after the file already moved) should fail loudly, not silently
    # re-move an already-quarantined file onto itself.
    norm = os.path.normpath(rel_path)
    first_segment = norm.split(os.sep)[0]
    if os.path.isabs(rel_path) or norm.startswith("..") or first_segment == "_quarantine":
        result["error"] = "invalid or already-quarantined path"
        print(json.dumps(result))
        log(f"{timestamp()}  REJECTED  {rel_path}  reason=invalid_path")
        sys.exit(0)

    src = os.path.join(HDD_ROOT, norm)
    dest = os.path.join(QUARANTINE_DIR, norm)
    s3_key = f"{S3_PREFIX}/{norm}"

    if not os.path.isfile(src):
        result["error"] = f"source file not found: {src}"
        print(json.dumps(result))
        log(f"{timestamp()}  FAILED  {norm}  reason=source_not_found")
        sys.exit(0)

    if os.path.exists(dest):
        result["error"] = f"destination already exists: {dest}"
        print(json.dumps(result))
        log(f"{timestamp()}  FAILED  {norm}  reason=dest_already_exists")
        sys.exit(0)

    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
    except OSError as e:
        result["error"] = f"move failed: {e}"
        print(json.dumps(result))
        log(f"{timestamp()}  FAILED  {norm}  reason=move_error:{e}")
        sys.exit(0)

    # Local move is now confirmed done. Only now touch S3 - never the other
    # way around, so a failed/partial run never leaves a duplicate deleted
    # from S3 while the local file still sits in its original spot.
    s3_status = "deleted"
    try:
        client = boto3.client("s3", region_name=REGION)
        client.delete_object(Bucket=BUCKET, Key=s3_key)
    except Exception as e:
        s3_status = f"error:{e}"

    result["ok"] = True
    result["moved_to"] = dest
    result["s3_key"] = s3_key
    result["s3_status"] = s3_status

    log(
        f"{timestamp()}  QUARANTINED  {norm}  ->  {dest}  "
        f"s3_key={s3_key}  s3_status={s3_status}"
    )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
