# videos/services.py
import boto3
from botocore.config import Config
from django.conf import settings


def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def upload_to_r2(file_obj, key):
    """Upload a file to Cloudflare R2. Returns public URL."""
    client = get_r2_client()
    client.upload_fileobj(
        file_obj,
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={
            'ContentType': getattr(file_obj, 'content_type', 'application/octet-stream')
        }
    )
    return f"{settings.R2_PUBLIC_URL}/{key}"


def delete_from_r2(key):
    """Delete a file from Cloudflare R2."""
    client = get_r2_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    
