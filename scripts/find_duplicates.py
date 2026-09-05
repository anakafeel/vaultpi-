#!/usr/bin/env python3
import json
import time
import resource
import boto3
import numpy as np

TABLE_NAME = "VaultPi-FileMetadata"
REGION = "us-east-1"
SIM_THRESHOLD = 0.95
REPORT_PATH = "/home/anakafeel/vaultpi/duplicate_report.txt"

def scan_table():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    keys = []
    vectors = []
    scanned = 0
    skipped = 0

    scan_kwargs = {
        "ProjectionExpression": "s3_key, embedding",
    }

    while True:
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            scanned += 1
            emb_str = item.get("embedding")
            s3_key = item.get("s3_key")
            if not emb_str or not s3_key:
                skipped += 1
                continue
            try:
                vec = json.loads(emb_str)
            except (json.JSONDecodeError, TypeError):
                skipped += 1
                continue
            if not vec or len(vec) != 1024:
                skipped += 1
                continue
            keys.append(s3_key)
            vectors.append(vec)

        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return keys, vectors, scanned, skipped


def main():
    overall_start = time.time()

    print("Scanning DynamoDB table (paginated)...")
    t0 = time.time()
    keys, vectors, scanned, skipped = scan_table()
    t1 = time.time()
    print(f"Scan complete in {t1 - t0:.1f}s: {scanned} items scanned, "
          f"{len(vectors)} valid embeddings, {skipped} skipped")

    if len(vectors) < 2:
        print("Not enough valid embeddings to compare. Exiting.")
        return

    print("Building embedding matrix...")
    t0 = time.time()
    matrix = np.array(vectors, dtype=np.float32)
    n = matrix.shape[0]
    t1 = time.time()
    print(f"Matrix built in {t1 - t0:.1f}s: shape={matrix.shape}")

    print("Normalizing vectors...")
    t0 = time.time()
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # guard against zero vectors (shouldn't happen, but be safe)
    normalized = matrix / norms
    t1 = time.time()
    print(f"Normalization done in {t1 - t0:.1f}s")

    print(f"Computing full {n}x{n} cosine similarity matrix "
          f"(~{n * (n - 1) // 2:,} unique pairs)... this may take a few minutes.")
    t0 = time.time()
    sim_matrix = normalized @ normalized.T
    t1 = time.time()
    print(f"Similarity matrix computed in {t1 - t0:.1f}s")

    print("Extracting duplicate pairs above threshold...")
    t0 = time.time()
    # Walk row-by-row instead of materializing full triu_indices (which would
    # allocate ~2GB+ of index arrays for ~109M pairs at n=14800). Only the
    # matches above threshold get kept, which is a tiny fraction of pairs.
    idx_i_list = []
    idx_j_list = []
    score_list = []
    for i in range(n - 1):
        row = sim_matrix[i, i + 1:]
        hits = np.nonzero(row >= SIM_THRESHOLD)[0]
        if hits.size:
            idx_i_list.append(np.full(hits.size, i, dtype=np.int32))
            idx_j_list.append(hits.astype(np.int32) + (i + 1))
            score_list.append(row[hits])

    if score_list:
        idx_i = np.concatenate(idx_i_list)
        idx_j = np.concatenate(idx_j_list)
        scores = np.concatenate(score_list)
        order = np.argsort(-scores)
        idx_i = idx_i[order]
        idx_j = idx_j[order]
        scores = scores[order]
    else:
        idx_i = np.array([], dtype=np.int32)
        idx_j = np.array([], dtype=np.int32)
        scores = np.array([], dtype=np.float32)
    t1 = time.time()
    print(f"Extraction/sort done in {t1 - t0:.1f}s: {len(scores)} pairs >= {SIM_THRESHOLD}")

    print(f"Writing report to {REPORT_PATH}...")
    t0 = time.time()
    with open(REPORT_PATH, "w") as f:
        for score, i, j in zip(scores, idx_i, idx_j):
            f.write(f"{score:.6f}  {keys[i]}  <->  {keys[j]}\n")
    t1 = time.time()
    print(f"Report written in {t1 - t0:.1f}s")

    overall_end = time.time()
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KB on Linux
    peak_mb = peak_kb / 1024

    print("\n=== SUMMARY ===")
    print(f"Total valid embeddings loaded: {len(vectors)}")
    print(f"Total duplicate pairs found (>= {SIM_THRESHOLD}): {len(scores)}")
    print(f"Total wall time: {overall_end - overall_start:.1f}s")
    print(f"Peak memory (RSS): {peak_mb:.1f} MB")
    print(f"\nTop 10 highest-confidence pairs:")
    for score, i, j in list(zip(scores, idx_i, idx_j))[:10]:
        print(f"  {score:.6f}  {keys[i]}  <->  {keys[j]}")


if __name__ == "__main__":
    main()
