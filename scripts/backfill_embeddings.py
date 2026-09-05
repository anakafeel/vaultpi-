import boto3
import json
import base64
import uuid
import time
import io
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import pillow_heif
from botocore.exceptions import ClientError

pillow_heif.register_heif_opener()

BUCKET = "saim-vaultpi-files"
PREFIX = "photos/"
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.heic')
CHECKPOINT_FILE = "/home/anakafeel/vaultpi/backfill_checkpoint.txt"
WORKERS = 4
MAX_DIMENSION = 2048  # Titan Multimodal Embeddings rejects images larger than this

s3 = boto3.client('s3', region_name='us-east-1')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('VaultPi-FileMetadata')

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def append_checkpoint(key):
    with open(CHECKPOINT_FILE, 'a') as f:
        f.write(key + '\n')

def list_all_keys():
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.rsplit('/', 1)[-1].startswith('._'):
                continue  # macOS AppleDouble resource-fork sidecar file, not a real image
            if key.lower().endswith(IMAGE_EXTENSIONS):
                yield key

def to_jpeg_bytes(image_bytes, key):
    """Converts any image (including HEIC) to JPEG bytes, resized to fit Bedrock's pixel limit."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')  # HEIC/PNG can be in a mode JPEG doesn't support
    if img.size[0] > MAX_DIMENSION or img.size[1] > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue()

def process_key(key, retries=3):
    for attempt in range(retries):
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=key)
            raw_bytes = obj['Body'].read()

            try:
                jpeg_bytes = to_jpeg_bytes(raw_bytes, key)
            except Exception as conv_err:
                return (key, False, f"Image conversion failed: {conv_err}")

            body = json.dumps({
                "inputImage": base64.b64encode(jpeg_bytes).decode('utf-8')
            })
            response = bedrock.invoke_model(
                modelId="amazon.titan-embed-image-v1",
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding', [])

            file_id = str(uuid.uuid4())
            table.put_item(Item={
                'file_id': file_id,
                's3_key': key,
                'tags': [],
                'embedding': json.dumps(embedding),
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'file_size': obj['ContentLength'],
                'was_heic': key.lower().endswith('.heic')
            })
            return (key, True, None)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'ValidationException':
                return (key, False, str(e))  # permanent client error, retrying won't help
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return (key, False, str(e))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return (key, False, str(e))

def main():
    done = load_checkpoint()
    all_keys = [k for k in list_all_keys() if k not in done]
    total = len(all_keys)
    print(f"Total to process: {total} (already done: {len(done)})")

    processed = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(process_key, key): key for key in all_keys}
        for future in as_completed(futures):
            key, success, error = future.result()
            if success:
                append_checkpoint(key)
                processed += 1
            else:
                failed += 1
                print(f"FAILED: {key} — {error}")
            if (processed + failed) % 100 == 0:
                print(f"Progress: {processed + failed}/{total} (success: {processed}, failed: {failed})")

    print(f"=== Backfill complete: {processed} succeeded, {failed} failed ===")

if __name__ == "__main__":
    main()
