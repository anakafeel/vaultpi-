import boto3
import json
import base64
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote_plus

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('VaultPi-FileMetadata')

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.heic')

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        if not key.lower().endswith(IMAGE_EXTENSIONS):
            print(f"Skipping non-image file: {key}")
            continue

        obj = s3.get_object(Bucket=bucket, Key=key)
        image_bytes = obj['Body'].read()

        labels = []
        try:
            rek_response = rekognition.detect_labels(
                Image={'Bytes': image_bytes},
                MaxLabels=10,
                MinConfidence=75
            )
            labels = [l['Name'] for l in rek_response['Labels']]
        except Exception as e:
            print(f"Rekognition failed for {key}: {e}")

        embedding = []
        try:
            body = json.dumps({
                "inputImage": base64.b64encode(image_bytes).decode('utf-8')
            })
            bedrock_response = bedrock.invoke_model(
                modelId="amazon.titan-embed-image-v1",
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(bedrock_response['body'].read())
            embedding = response_body.get('embedding', [])
        except Exception as e:
            print(f"Bedrock embedding failed for {key}: {e}")

        file_id = str(uuid.uuid4())
        table.put_item(Item={
            'file_id': file_id,
            's3_key': key,
            'tags': labels,
            'embedding': json.dumps(embedding),
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
            'file_size': obj['ContentLength']
        })

        print(f"Processed {key}: {len(labels)} labels, embedding length {len(embedding)}")

    return {'statusCode': 200, 'body': json.dumps('Processing complete')}
