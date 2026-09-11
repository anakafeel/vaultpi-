#!/usr/bin/env python3
import argparse
import json
import os
import time
import boto3
import numpy as np

TABLE_NAME = "VaultPi-FileMetadata"
REGION = "us-east-1"
MODEL_ID = "amazon.titan-embed-image-v1"
TOP_K = 10

# A full table.scan() over ~14,800 items takes ~55-60s on the Pi (dozens of
# paginated round trips to us-east-1), which was making the n8n Photo Search
# webhook time out in practice. find_duplicates.py already sidesteps this
# same scan by writing a report once and reading it back cheaply - this
# applies the same idea to search: cache the scan result on disk and only
# re-scan when it's older than CACHE_MAX_AGE, instead of on every query.
# Cached under logs/, not next to the script - that's the one subtree the
# n8n container mounts read-write (see pi-configs/n8n/docker-compose.yml);
# everything else under ~/vaultpi is mounted read-only there.
#
# .npz (numpy's binary format), not JSON: the ~14,800 x 1024 float matrix
# serialized as JSON text is ~200MB and took ~11s just to re-parse on the
# Pi's CPU on every request - almost as much overhead as the scan it was
# meant to avoid. np.load on the same data is well under a second.
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "embedding_cache.npz"
)
CACHE_MAX_AGE = 6 * 3600  # matches the sync/backfill cadence closely enough


def embed_query(text):
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = json.dumps({"inputText": text})
    resp = client.invoke_model(
        modelId=MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(resp["body"].read())
    embedding = result.get("embedding")
    if not embedding or len(embedding) != 1024:
        raise RuntimeError(f"Unexpected embedding response: {result}")
    return np.array(embedding, dtype=np.float32)


def scan_table():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    keys = []
    vectors = []
    scan_kwargs = {"ProjectionExpression": "s3_key, embedding"}

    while True:
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            emb_str = item.get("embedding")
            s3_key = item.get("s3_key")
            if not emb_str or not s3_key:
                continue
            try:
                vec = json.loads(emb_str)
            except (json.JSONDecodeError, TypeError):
                continue
            if not vec or len(vec) != 1024:
                continue
            keys.append(s3_key)
            vectors.append(vec)

        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return keys, vectors


def load_embeddings():
    if os.path.exists(CACHE_PATH):
        age = time.time() - os.path.getmtime(CACHE_PATH)
        if age < CACHE_MAX_AGE:
            try:
                with np.load(CACHE_PATH, allow_pickle=False) as cached:
                    return list(cached["keys"]), cached["vectors"]
            except (OSError, KeyError, ValueError):
                pass  # fall through and re-scan below

    keys, vectors = scan_table()
    matrix = np.array(vectors, dtype=np.float32)
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    # Written via a same-directory temp file + os.replace (atomic on POSIX)
    # rather than straight to CACHE_PATH - two overlapping search requests
    # both scanning on a cold/expired cache would otherwise interleave their
    # writes into the same file and corrupt it for both.
    tmp_path = f"{CACHE_PATH}.{os.getpid()}.tmp"
    with open(tmp_path, "wb") as f:
        np.savez(f, keys=np.array(keys), vectors=matrix)
    os.replace(tmp_path, CACHE_PATH)
    return keys, matrix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="text query")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print results as a JSON array instead of human-readable text",
    )
    args = parser.parse_args()
    query = args.query

    if not args.json:
        print(f"Query: {query!r}")
    t0 = time.time()
    query_vec = embed_query(query)
    if not args.json:
        print(f"Query embedded in {time.time() - t0:.2f}s")

    t0 = time.time()
    keys, vectors = load_embeddings()
    if not args.json:
        print(f"Loaded {len(keys)} stored embeddings in {time.time() - t0:.1f}s")

    matrix = np.array(vectors, dtype=np.float32)

    query_norm = query_vec / np.linalg.norm(query_vec)
    matrix_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix_norms[matrix_norms == 0] = 1.0
    matrix_normalized = matrix / matrix_norms

    sims = matrix_normalized @ query_norm

    top_idx = np.argsort(-sims)[:TOP_K]

    if args.json:
        results = [
            {"s3_key": keys[idx], "score": round(float(sims[idx]), 4)}
            for idx in top_idx
        ]
        print(json.dumps(results))
    else:
        print(f"\nTop {TOP_K} matches:")
        for rank, idx in enumerate(top_idx, 1):
            print(f"  {rank:2d}. {sims[idx]:.4f}  {keys[idx]}")


if __name__ == "__main__":
    main()
