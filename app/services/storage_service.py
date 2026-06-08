
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# Allowed MIME types for logo upload
ALLOWED_LOGO_MIME_TYPES = {"image/png", "image/jpeg"}
MIME_TO_EXT = {"image/png": "png", "image/jpeg": "jpg"}

# Max logo file size: 2 MB
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024


class StorageService:
    """
    Handles file operations against Supabase Storage (S3-compatible).
    All methods are stateless — a new boto3 client is built per call
    so there are no connection-lifetime issues in async workers.
    """

    def _get_client(self):
        """Build and return a boto3 S3 client pointed at Supabase Storage."""
        supabase_s3_endpoint = f"{settings.supabase_url}/storage/v1/s3"

        return boto3.client(
            "s3",
            endpoint_url=supabase_s3_endpoint,
            aws_access_key_id=settings.supabase_s3_access_key,
            aws_secret_access_key=settings.supabase_s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="ap-south-1",  # Supabase requires a region; value is ignored
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload_logo(self, hospital_id: str, file: UploadFile) -> str:
        """
        Upload a hospital logo to Supabase Storage.

        - Validates MIME type (PNG / JPEG only) and file size (≤ 2 MB).
        - Stored at:  hospitals/{hospital_id}/logo.{ext}
        - Overwrites any previous logo for the same hospital.

        Returns the public URL of the uploaded file.
        Raises HTTPException on validation failure or upload error.
        """
        self._validate_logo(file)

        content = await file.read()
        self._validate_size(content)

        ext = MIME_TO_EXT[file.content_type]
        object_key = f"hospitals/{hospital_id}/logo.{ext}"

        try:
            client = self._get_client()
            client.put_object(
                Bucket=settings.supabase_bucket_name,
                Key=object_key,
                Body=content,
                ContentType=file.content_type,
                # Supabase Storage respects Cache-Control headers
                CacheControl="public, max-age=31536000",
            )
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Storage upload failed: {error_code}",
            ) from exc

        public_url = self._build_public_url(object_key)
        return public_url

    def delete_file(self, object_key: str) -> None:
        """
        Delete a file from Supabase Storage by its object key.

        object_key examples:
            hospitals/abc-123/logo.png
            hospitals/abc-123/logo.jpg

        Silently succeeds if the file does not exist (S3 DELETE is idempotent).
        Raises HTTPException on unexpected storage errors.
        """
        try:
            client = self._get_client()
            client.delete_object(
                Bucket=settings.supabase_bucket_name,
                Key=object_key,
            )
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Storage delete failed: {error_code}",
            ) from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_logo(file: UploadFile) -> None:
        """Raise 422 if MIME type is not PNG or JPEG."""
        if file.content_type not in ALLOWED_LOGO_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported file type '{file.content_type}'. "
                    "Only PNG and JPEG images are accepted."
                ),
            )

    @staticmethod
    def _validate_size(content: bytes) -> None:
        """Raise 413 if file exceeds MAX_LOGO_SIZE_BYTES (2 MB)."""
        if len(content) > MAX_LOGO_SIZE_BYTES:
            limit_mb = MAX_LOGO_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Logo file must be ≤ {limit_mb} MB.",
            )

    @staticmethod
    def _build_public_url(object_key: str) -> str:
        """
        Construct the public URL for an object in the Supabase bucket.

        Format: {SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{object_key}
        """
        return (
            f"{settings.supabase_url}/storage/v1/object/public/"
            f"{settings.supabase_bucket_name}/{object_key}"
        )


# Singleton — import and use directly in routers / other services
storage_service = StorageService()
