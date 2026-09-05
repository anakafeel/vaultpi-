#!/usr/bin/env python3
import sys
import json
import time
import boto3
import numpy as np

TABLE_NAME = "VaultPi-FileMetadata"
REGION = "us-east-1"
MODEL_ID = "amazon.titan-embed-image-v1"
TOP_K = 10


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


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 search_photos.py \"<text query>\"")
        sys.exit(1)
    query = sys.argv[1]

    print(f"Query: {query!r}")
    t0 = time.time()
    query_vec = embed_query(query)
    print(f"Query embedded in {time.time() - t0:.2f}s")

    t0 = time.time()
    keys, vectors = scan_table()
    print(f"Scanned {len(keys)} stored embeddings in {time.time() - t0:.1f}s")

    matrix = np.array(vectors, dtype=np.float32)

    query_norm = query_vec / np.linalg.norm(query_vec)
    matrix_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix_norms[matrix_norms == 0] = 1.0
    matrix_normalized = matrix / matrix_norms

    sims = matrix_normalized @ query_norm

    top_idx = np.argsort(-sims)[:TOP_K]

    print(f"\nTop {TOP_K} matches:")
    for rank, idx in enumerate(top_idx, 1):
        print(f"  {rank:2d}. {sims[idx]:.4f}  {keys[idx]}")


if __name__ == "__main__":
    main()
