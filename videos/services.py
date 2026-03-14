# videos/services.py
import os
import shutil
from django.conf import settings


def upload_to_r2(file_obj, key):
    """
    LOCAL STORAGE (development only).
    Saves file to media/ folder instead of Cloudflare R2.
    Replace this entire function with R2 logic when ready.
    """
    # Build local path mirroring the R2 key structure
    local_path = os.path.join(settings.MEDIA_ROOT, key)

    # Create directories if they don't exist
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Save the file
    with open(local_path, 'wb') as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)

    # Return a local URL that Django can serve
    return f"{settings.MEDIA_URL}{key}"


def delete_from_r2(key):
    """
    LOCAL STORAGE (development only).
    Deletes file from media/ folder.
    """
    local_path = os.path.join(settings.MEDIA_ROOT, key)
    if os.path.exists(local_path):
        os.remove(local_path)
        
