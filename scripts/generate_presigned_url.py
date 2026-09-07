#!/usr/bin/env python3
import argparse
import json
import sys

import boto3

BUCKET = "saim-vaultpi-files"
REGION = "us-east-1"
EXPIRES_IN = 3600  # 1 hour - just for viewing search/dedup results, not a permanent link


def load_items():
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="*", help="S3 keys (if omitted, read JSON from stdin)")
    args = parser.parse_args()

    if args.keys:
        return [{"s3_key": k} for k in args.keys]

    data = json.load(sys.stdin)
    if isinstance(data, dict):
        data = [data]
    items = []
    for entry in data:
        if isinstance(entry, str):
            items.append({"s3_key": entry})
        else:
            items.append(dict(entry))
    return items


def main():
    items = load_items()
    client = boto3.client("s3", region_name=REGION)

    for item in items:
        item["url"] = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": item["s3_key"]},
            ExpiresIn=EXPIRES_IN,
        )

    print(json.dumps(items))


if __name__ == "__main__":
    main()
