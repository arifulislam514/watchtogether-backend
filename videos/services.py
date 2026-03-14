# videos/services.py
import boto3
import os
from django.conf import settings
from botocore.config import Config


def get_r2_client():
    """Returns a boto3 S3 client configured for Cloudflare R2"""
    return boto3.client(
        's3',
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


def upload_to_r2(file_obj, key):
    """
    Uploads a file to Cloudflare R2.
    Returns the public URL of the uploaded file.
    """
    client = get_r2_client()
    client.upload_fileobj(
        file_obj,
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={'ContentType': getattr(file_obj, 'content_type', 'application/octet-stream')}
    )
    return f"{settings.R2_ENDPOINT_URL}/{settings.R2_BUCKET_NAME}/{key}"


def delete_from_r2(key):
    """Deletes a file from Cloudflare R2"""
    client = get_r2_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    
