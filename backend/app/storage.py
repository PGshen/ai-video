import io
from datetime import timedelta
from minio import Minio
from app.config import settings


def _get_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    client = _get_client()
    _ensure_bucket(client)
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_to_file(key: str, local_path: str) -> None:
    client = _get_client()
    client.fget_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        file_path=local_path,
    )


def get_presigned_url(key: str, expires_seconds: int = 3600) -> str:
    # Signed against the publicly reachable endpoint (e.g. ai-video.zero-zero.cc) rather than
    # MINIO_ENDPOINT (e.g. minio:9000), which only resolves inside the Docker network.
    # region is pinned explicitly because presigned_get_object otherwise calls GetBucketLocation
    # against this same endpoint to discover it — a real network request the container can't
    # make against the public endpoint (only the internal one is reachable from here).
    client = Minio(
        settings.MINIO_PUBLIC_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_PUBLIC_SECURE,
        region="us-east-1",
    )
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        expires=timedelta(seconds=expires_seconds),
    )
